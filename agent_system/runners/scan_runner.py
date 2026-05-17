from agent_system.data.decisions_store import save_decision

def _prefilter_by_volume_and_extremes(binance, top_volume=30, top_funding=10,
                                        top_position_dev=10):
    """简化预筛: 取体量 top N, 在其中再选费率/持仓多空比极端者并集。"""
    tickers = binance.get_24h_ticker()
    ticker_map = {t["symbol"]: float(t.get("quoteVolume", 0))
                   for t in tickers if t.get("symbol", "").endswith("USDT")}
    top_vol_symbols = sorted(ticker_map.keys(), key=lambda s: ticker_map[s], reverse=True)[:top_volume]

    funding = binance.get_premium_index()
    fmap = {f["symbol"]: float(f.get("lastFundingRate", 0))
             for f in funding if f.get("symbol") in top_vol_symbols}
    by_funding = sorted(fmap.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_funding]

    pos_dev = []
    for s in top_vol_symbols:
        try:
            pr = binance.get_top_long_short_position_ratio(s, period="1h", limit=1)
            ratio = float(pr[-1]["longShortRatio"]) if pr else 1.0
            pos_dev.append((s, abs(ratio - 1.0)))
        except Exception:
            continue
    by_pos = sorted(pos_dev, key=lambda kv: kv[1], reverse=True)[:top_position_dev]

    out = []
    for s, _ in by_funding + by_pos:
        if s not in out:
            out.append(s)
    return out

class ScanRunner:
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
        try:
            limit = self.cfg["scheduler"]["scan_max_candidates"]
            return _prefilter_by_volume_and_extremes(
                self.binance, top_volume=30, top_funding=10, top_position_dev=10
            )[:limit]
        except Exception as e:
            print(f"[scan] prefilter failed: {e}; fallback")
            return ["BTCUSDT", "ETHUSDT"]

    def run_once(self) -> list:
        candidates = self._candidates()
        print(f"[scan] candidates: {candidates}")
        cards = []
        for symbol in candidates:
            try:
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                card = self.orch.run(symbol=symbol, mode="lean", data_pack=pack)
                tags = pack.get("tags", [])
                did = save_decision(self.db_path, symbol=symbol, trigger_mode="scan",
                                    card=card, tags=tags, audit_path="")
                card["decision_id"] = did
                cards.append(card)
            except Exception as e:
                print(f"[scan] {symbol} failed: {e}")
        cards.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        top = cards[:5]
        if self.push and top:
            self.push.push_scan_results(top)
        return top
