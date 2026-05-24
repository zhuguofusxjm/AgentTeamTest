from agent_system.data.decisions_store import save_decision

def _prefilter_by_volume_and_extremes(binance, top_volume=30, top_funding=10,
                                        top_position_dev=10, top_price_change=10,
                                        top_oi_growth=10, top_volume_anomaly=10):
    """全市场扫描的候选预筛——"先大后偏" 两层过滤。

    流程:
    1. 第一层(体量过滤):取全市场 24h 行情,按 quoteVolume 倒序,
       只保留前 top_volume 个 USDT 永续。这一步过滤掉小盘币的脏数据。
    2. 第二层(极端筛选)在前 30 大里再选五类异常:
       a) 资金费率最极端(拥挤): |费率| 倒序前 top_funding 个
       b) 持仓多空比最极端(站队): |ratio - 1.0| 倒序前 top_position_dev 个
       c) 24h 涨跌幅最大(动量): |priceChangePercent| 倒序前 top_price_change 个
       d) OI 增长率最高(资金涌入): (oi_now - oi_24h_ago) / oi_24h_ago 倒序前 top_oi_growth 个
       e) 成交量异动(相对自身均值): vol_24h / avg_7d 倒序前 top_volume_anomaly 个
    3. 合并去重,返回候选 symbol 列表。

    参数:
        binance: BinanceClient 实例
        top_volume: 第一层保留的体量 Top N(默认 30)
        top_funding/top_position_dev/...: 第二层各类极端的 Top N(默认各 10)

    返回:
        list[str],候选 symbol(各维度并集去重,最多 5*top_N,有重叠时更少)
    """
    # ---- 第一层:体量 Top N ----
    # 24h_ticker 一次性返回全市场,顺便提取 priceChangePercent(动量维度免费)
    tickers = binance.get_24h_ticker()
    ticker_map = {}
    price_change_map = {}
    for t in tickers:
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        ticker_map[sym] = float(t.get("quoteVolume", 0))
        price_change_map[sym] = float(t.get("priceChangePercent", 0))
    top_vol_symbols = sorted(ticker_map.keys(), key=lambda s: ticker_map[s], reverse=True)[:top_volume]
    dim_map = {}  # symbol -> set of dim keys

    # ---- 第二层 A:费率极端 ----
    # premium_index 一次返回全部 symbol 的当前费率,只取 top_vol_symbols 子集
    funding = binance.get_premium_index()
    fmap = {f["symbol"]: float(f.get("lastFundingRate", 0))
             for f in funding if f.get("symbol") in top_vol_symbols}
    by_funding = sorted(fmap.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_funding]
    for s, _ in by_funding:
        dim_map.setdefault(s, set()).add("funding")

    # ---- 第二层 B:大户多空比极端 ----
    # 注意:这里是串行调用,每个 symbol 一次 API 请求(top_volume 次)
    # 后续如有性能问题,可改为 ThreadPoolExecutor 并发
    pos_dev = []
    for s in top_vol_symbols:
        try:
            pr = binance.get_top_long_short_position_ratio(s, period="1h", limit=1)
            ratio = float(pr[-1]["longShortRatio"]) if pr else 1.0
            # 偏离 1.0 越多 = 多空越不平衡
            pos_dev.append((s, abs(ratio - 1.0)))
        except Exception:
            # 单个 symbol 失败不影响其他,跳过即可
            continue
    by_pos = sorted(pos_dev, key=lambda kv: kv[1], reverse=True)[:top_position_dev]
    for s, _ in by_pos:
        dim_map.setdefault(s, set()).add("position")

    # ---- 第二层 C:价格动量(24h 涨跌幅最大) ----
    # 数据已在第一层 ticker 中拿到,无额外 API 调用
    pct_in_top = [(s, price_change_map[s]) for s in top_vol_symbols if s in price_change_map]
    by_price = sorted(pct_in_top, key=lambda kv: abs(kv[1]), reverse=True)[:top_price_change]
    for s, _ in by_price:
        dim_map.setdefault(s, set()).add("price")

    # ---- 第二层 D:OI 增长率(近 24h 资金涌入) ----
    # 用 1h 周期 limit=25,头尾对比算 24h 增长率;失败跳过
    oi_growth = []
    for s in top_vol_symbols:
        try:
            oi = binance.get_open_interest_hist(s, period="1h", limit=25)
            if not oi or len(oi) < 2:
                continue
            oi_now = float(oi[-1].get("sumOpenInterest", 0))
            oi_old = float(oi[0].get("sumOpenInterest", 0))
            if oi_old <= 0:
                continue
            growth = (oi_now - oi_old) / oi_old
            oi_growth.append((s, growth))
        except Exception:
            continue
    # 只取增长(正向),萎缩不进候选
    by_oi = sorted([x for x in oi_growth if x[1] > 0], key=lambda kv: kv[1], reverse=True)[:top_oi_growth]
    for s, _ in by_oi:
        dim_map.setdefault(s, set()).add("oi_growth")

    # ---- 第二层 E:成交量异动(24h vs 前 7 天均值) ----
    # 用 1d 周期 limit=8 算 vol_24h / avg_prev_7d
    vol_anomaly = []
    for s in top_vol_symbols:
        try:
            kl = binance.get_klines(s, interval="1d", limit=8)
            if not kl or len(kl) < 8:
                continue
            # K 线第 7 列(index 7)是 quote_volume
            vols = [float(k[7]) for k in kl]
            vol_24h = vols[-1]
            avg_prev_7d = sum(vols[:-1]) / 7
            if avg_prev_7d <= 0:
                continue
            ratio = vol_24h / avg_prev_7d
            vol_anomaly.append((s, ratio))
        except Exception:
            continue
    # 只取放大(>1),萎缩不进候选
    by_vol = sorted([x for x in vol_anomaly if x[1] > 1.0], key=lambda kv: kv[1], reverse=True)[:top_volume_anomaly]
    for s, _ in by_vol:
        dim_map.setdefault(s, set()).add("volume_anomaly")

    # ---- 合并去重(保留首次出现的顺序) ----
    seen = set()
    out = []
    for s, _ in by_funding + by_pos + by_price + by_oi + by_vol:
        if s not in seen:
            seen.add(s)
            out.append({"symbol": s, "dims": sorted(dim_map.get(s, set()))})
    return out

class ScanRunner:
    """全市场定时扫描——每 N 分钟跑一次,挑出极端候选 → 跑 lean 圆桌 → 推送 top 5。

    在 start.py 中作为后台循环之一启动。
    扫描间隔由 config.yaml 的 scheduler.scan_interval_min 控制(默认 240 分钟/4h)。
    """

    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer,
                 push_client=None):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer
        self.push = push_client

    def _candidates(self) -> list:
        """挑选本轮扫描的候选 symbol 列表。

        失败时降级返回 [BTCUSDT, ETHUSDT],保证扫描不中断。
        最终数量受 scheduler.scan_max_candidates(默认 10)限制。
        """
        try:
            limit = self.cfg["scheduler"]["scan_max_candidates"]
            return _prefilter_by_volume_and_extremes(
                self.binance, top_volume=30,
                top_funding=10, top_position_dev=10,
                top_price_change=10, top_oi_growth=10, top_volume_anomaly=10,
            )[:limit]
        except Exception as e:
            print(f"[scan] prefilter failed: {e}; fallback")
            return [{"symbol": "BTCUSDT", "dims": []}, {"symbol": "ETHUSDT", "dims": []}]

    def run_once(self) -> list:
        """执行一轮扫描:挑候选 → 逐个跑 lean 圆桌 → 入库 → 推送 top 5。

        返回 confidence 倒序的前 5 张决策卡片。
        单个 symbol 失败不会影响其他(异常被吞,只 print 警告)。
        """
        candidates = self._candidates()
        print(f"[scan] candidates: {candidates}")
        cards = []
        for item in candidates:
            symbol = item["symbol"] if isinstance(item, dict) else item
            dims = item.get("dims", []) if isinstance(item, dict) else []
            try:
                # 每个候选都拉一份完整 DataPack,跑 lean 模式(7 mate, 2 轮)
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                card = self.orch.run(symbol=symbol, mode="lean", data_pack=pack)
                tags = pack.get("tags", [])
                # 入库 decisions 表,后续会被 status_tracker / retrospective 使用
                # audit_path 从 card 取(由 orchestrator.finalize 写入),
                # 这样前端 /api/debate/<id> 才能调出 12 位分析师的辩论流
                audit_path = card.get("audit_path") or ""
                did = save_decision(self.db_path, symbol=symbol, trigger_mode="scan",
                                    card=card, tags=tags, audit_path=audit_path,
                                    prefilter_tags=dims if dims else None)
                card["decision_id"] = did
                cards.append(card)
            except Exception as e:
                print(f"[scan] {symbol} failed: {e}")
        # 按 confidence 排序,只推送最强的 5 个,避免 push 噪声
        cards.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        top = cards[:5]
        if self.push and top:
            self.push.push_scan_results(top)
        return top
