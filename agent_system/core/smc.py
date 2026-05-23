"""Smart Money Concepts - 移植自 LuxAlgo Pine 指标。

输入一段 K 线,输出 swing/BOS/CHoCH/Order Block/FVG/EQH-EQL/Premium-Discount。

核心规则参考 docs(spec 已在 chat 锁定):
- swing length: 50, internal length: 5, eqhl length: 3, eqhl threshold: 0.1*ATR
- 高波动过滤: (high-low) >= 2*ATR(200) 时翻转 parsedHigh/Low
- OB 失效: HIGHLOW 模式 (任一 bar 极值穿透 OB 即失效)
- FVG 自适应阈值, 完全填补失效
- Premium/Discount: 5%/95% 切, 47.5-52.5% Equilibrium
"""

BULLISH_LEG = 1   # 当前处于上升腿(刚确认了一个 swing low)
BEARISH_LEG = 0   # 当前处于下降腿(刚确认了一个 swing high)
BULLISH = 1       # 多头方向
BEARISH = -1      # 空头方向


class _Pivot:
    """记录一个 swing 极值点的状态。

    Pine 中对应 pivot UDT。每次新 swing 出现时更新 current_level,
    旧值移到 last_level。crossed 标记该 pivot 是否已被 close 穿越(触发 BOS/CHoCH)。
    """
    __slots__ = ("current_level", "last_level", "crossed", "bar_time", "bar_index")

    def __init__(self):
        self.current_level = None   # 当前 swing 极值价格
        self.last_level = None      # 上一个 swing 极值(用于 EQH/EQL 对比)
        self.crossed = False        # 是否已被穿越(穿越后不再重复触发)
        self.bar_time = None        # 该 swing 所在 bar 的时间戳
        self.bar_index = None       # 该 swing 所在 bar 的索引


def _calc_atr_series(highs, lows, closes, period=200):
    """计算每根 bar 的 ATR(Average True Range)序列。

    对前 period 根不足的部分用已有数据的均值(渐进式),
    之后用标准 SMA(period) 滑窗。返回与输入等长的 list。
    """
    n = len(highs)
    trs = []
    for i in range(n):
        if i == 0:
            trs.append(highs[0] - lows[0])
        else:
            # True Range = max(当根振幅, |high-前close|, |low-前close|)
            trs.append(max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            ))
    out = [0.0] * n
    for i in range(n):
        if i < period:
            # 数据不足 period 根时,用已有数据的均值
            out[i] = sum(trs[: i + 1]) / (i + 1)
        else:
            out[i] = sum(trs[i - period + 1 : i + 1]) / period
    return out


def _is_swing_at(highs, lows, idx, size):
    """idx 处是否是 swing high/low - 它后面 size 根都没超过它."""
    n = len(highs)
    if idx < 0 or idx + size >= n:
        return False, False
    right_high = max(highs[idx + 1 : idx + size + 1])
    right_low = min(lows[idx + 1 : idx + size + 1])
    is_high = highs[idx] > right_high
    is_low = lows[idx] < right_low
    return is_high, is_low


def _store_ob(obs, bias, pivot, parsed_highs, parsed_lows, times, current_idx):
    """在 BOS/CHoCH 触发时,回溯找 Order Block 并存入列表。

    Order Block 定义:从 pivot 所在 bar 到当前 bar 之间,
    找 parsed 极值(bearish 找最高、bullish 找最低)那根 bar 的 [low, high] 区间。
    这代表机构在该区间有大量挂单痕迹。

    obs: 存储 OB 的列表(会被原地修改)
    bias: BULLISH 或 BEARISH,表示这个 OB 的方向
    pivot: 被穿越的那个 swing pivot
    parsed_highs/parsed_lows: 经过高波动过滤后的 high/low 序列
    current_idx: 当前 bar 索引(BOS/CHoCH 发生的位置)
    """
    p_idx = pivot.bar_index
    if p_idx is None or p_idx >= current_idx:
        return
    if bias == BEARISH:
        # bearish OB: 找 pivot→current 区间内 parsed_high 最大的那根
        seg = parsed_highs[p_idx:current_idx]
        if not seg:
            return
        rel = seg.index(max(seg))
    else:
        # bullish OB: 找 pivot→current 区间内 parsed_low 最小的那根
        seg = parsed_lows[p_idx:current_idx]
        if not seg:
            return
        rel = seg.index(min(seg))
    parsed_idx = p_idx + rel
    obs.insert(0, {
        "bias": bias,
        "bar_high": parsed_highs[parsed_idx],
        "bar_low": parsed_lows[parsed_idx],
        "bar_time": times[parsed_idx],
        "bar_index": parsed_idx,
    })
    # 最多保留 100 个(内存安全),实际输出时只取 ob_max 个
    if len(obs) > 100:
        obs.pop()


def _purge_obs(obs, bar_high, bar_low, bar_close):
    """清除已失效的 Order Block(HIGHLOW 模式)。

    失效规则:
    - bearish OB: 当前 bar 的 high 穿透了 OB 的 bar_high → 失效(多头突破了空头阻力)
    - bullish OB: 当前 bar 的 low 穿透了 OB 的 bar_low → 失效(空头击穿了多头支撑)
    """
    out = []
    for ob in obs:
        if ob["bias"] == BEARISH and bar_high > ob["bar_high"]:
            continue  # bearish OB 被向上穿透,失效
        if ob["bias"] == BULLISH and bar_low < ob["bar_low"]:
            continue  # bullish OB 被向下穿透,失效
        out.append(ob)
    return out


def _purge_fvgs(fvgs, bar_high, bar_low):
    """清除已被完全填补的 Fair Value Gap。

    失效规则(完全填补):
    - bullish FVG: 当前 bar 的 low < FVG.bottom → 价格回填了整个缺口
    - bearish FVG: 当前 bar 的 high > FVG.top → 价格回填了整个缺口
    """
    out = []
    for fvg in fvgs:
        if fvg["bias"] == BULLISH and bar_low < fvg["bottom"]:
            continue
        if fvg["bias"] == BEARISH and bar_high > fvg["top"]:
            continue
        out.append(fvg)
    return out


def compute_smc(klines, swing_length=50, internal_length=5, eqhl_length=3,
                eqhl_threshold=0.1, ob_max=5, fvg_max=10, atr_period=200):
    """计算 Smart Money Concepts 全部指标。

    参数:
        klines: K 线列表(升序),每根含 open/high/low/close/open_time
        swing_length: swing 结构的确认长度(右侧 N 根不超过才算 swing)
        internal_length: internal 结构的确认长度(更短=更敏感)
        eqhl_length: Equal High/Low 的确认长度
        eqhl_threshold: EQH/EQL 判定阈值,两个 swing 价差 < threshold*ATR 才算"相等"
        ob_max: 输出中最多保留的 Order Block 数量
        fvg_max: 输出中最多保留的 FVG 数量
        atr_period: ATR 计算周期

    返回:
        dict,包含 swing/internal/order_blocks/fvg/equal_highs/equal_lows/zone 等。
        如果数据不足,返回 {"_status": "insufficient_data", ...}。
    """
    n = len(klines)
    min_bars = swing_length + internal_length + 2
    if n < min_bars:
        return {"_status": "insufficient_data", "n_bars": n, "min_required": min_bars}

    # ===== 预处理:提取价格序列 + 计算 ATR =====
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    closes = [k["close"] for k in klines]
    times = [k["open_time"] for k in klines]
    atr_series = _calc_atr_series(highs, lows, closes, period=atr_period)

    # ===== 高波动 bar 过滤 =====
    # 当某根 bar 的振幅 >= 2*ATR 时,视为"高波动 bar"(插针/暴力拉升),
    # 翻转其 parsedHigh/Low,降低对 OB 极值定位的干扰。
    # 例:一根巨阴线,其 high 不应作为 bearish OB 的上沿(可能是假突破)。
    parsed_highs = []
    parsed_lows = []
    for i in range(n):
        atr_i = atr_series[i] if atr_series[i] > 0 else (highs[i] - lows[i])
        if (highs[i] - lows[i]) >= 2 * atr_i:
            # 高波动 bar:翻转(用 low 当 parsedHigh,用 high 当 parsedLow)
            parsed_highs.append(lows[i])
            parsed_lows.append(highs[i])
        else:
            parsed_highs.append(highs[i])
            parsed_lows.append(lows[i])

    # ===== 状态变量初始化 =====
    # swing/internal/eq 各自维护一对 high/low pivot
    swing_high = _Pivot()       # swing 级别的最近高点
    swing_low = _Pivot()        # swing 级别的最近低点
    internal_high = _Pivot()    # internal 级别的最近高点(更敏感)
    internal_low = _Pivot()     # internal 级别的最近低点
    eq_high = _Pivot()          # 用于 EQH 检测的最近高点
    eq_low = _Pivot()           # 用于 EQL 检测的最近低点
    swing_trend_bias = 0        # swing 级别的趋势方向(BULLISH/BEARISH/0=未定)
    internal_trend_bias = 0     # internal 级别的趋势方向

    swing_obs = []              # swing 级别的 Order Block 列表
    internal_obs = []           # internal 级别的 Order Block 列表
    fvgs = []                   # Fair Value Gap 列表
    eqhs = []                   # Equal Highs 列表
    eqls = []                   # Equal Lows 列表
    swing_events = []           # swing 级别的 BOS/CHoCH 事件记录
    internal_events = []        # internal 级别的 BOS/CHoCH 事件记录

    # trailing 极值:实时跟踪最高/最低点,用于 Premium/Discount zone
    trailing_top = highs[0]
    trailing_bottom = lows[0]
    trailing_top_time = times[0]
    trailing_bottom_time = times[0]
    trailing_anchor_time = times[0]
    trailing_anchor_index = 0

    # leg 状态:记录上一次确认的 leg 方向,用于检测 leg 切换(= 新 swing 出现)
    swing_leg_prev = 0
    internal_leg_prev = 0

    def update_pivot_from_swing(p, level, bar_time, bar_index):
        """更新 pivot:旧值移到 last_level,新值写入 current_level,重置 crossed。"""
        p.last_level = p.current_level
        p.current_level = level
        p.crossed = False
        p.bar_time = bar_time
        p.bar_index = bar_index

    # ===== 主循环:逐 bar 扫描 =====
    for i in range(n):
        # trailing 实时更新 (Pine: updateTrailingExtremes)
        if highs[i] > trailing_top:
            trailing_top = highs[i]
            trailing_top_time = times[i]
        if lows[i] < trailing_bottom:
            trailing_bottom = lows[i]
            trailing_bottom_time = times[i]

        # purge 当前 bar 失效的 FVG / OB
        fvgs = _purge_fvgs(fvgs, highs[i], lows[i])
        swing_obs = _purge_obs(swing_obs, highs[i], lows[i], closes[i])
        internal_obs = _purge_obs(internal_obs, highs[i], lows[i], closes[i])

        # ---- 检测 swing pivot (size = swing_length) ----
        # 原理:看 bar[i - swing_length] 是否是 swing point。
        # 即:它后面的 swing_length 根 bar 的 high 都没超过它(= swing high),
        # 或它后面的 swing_length 根 bar 的 low 都没跌破它(= swing low)。
        # 当 leg 方向切换时(从涨转跌 or 跌转涨),记录新的 swing pivot。
        s_target = i - swing_length
        if s_target >= 0:
            right_high = max(highs[s_target + 1 : i + 1])
            right_low = min(lows[s_target + 1 : i + 1])
            new_high = highs[s_target] > right_high
            new_low = lows[s_target] < right_low
            cur_leg = swing_leg_prev
            if new_high:
                cur_leg = BEARISH_LEG
            elif new_low:
                cur_leg = BULLISH_LEG
            if cur_leg != swing_leg_prev:
                if cur_leg == BULLISH_LEG:
                    update_pivot_from_swing(swing_low, lows[s_target], times[s_target], s_target)
                    trailing_bottom = lows[s_target]
                    trailing_bottom_time = times[s_target]
                    trailing_anchor_time = times[s_target]
                    trailing_anchor_index = s_target
                else:
                    update_pivot_from_swing(swing_high, highs[s_target], times[s_target], s_target)
                    trailing_top = highs[s_target]
                    trailing_top_time = times[s_target]
                    trailing_anchor_time = times[s_target]
                    trailing_anchor_index = s_target
            swing_leg_prev = cur_leg

        # ---- 检测 internal pivot (size = internal_length) ----
        in_target = i - internal_length
        if in_target >= 0:
            right_high = max(highs[in_target + 1 : i + 1])
            right_low = min(lows[in_target + 1 : i + 1])
            new_high = highs[in_target] > right_high
            new_low = lows[in_target] < right_low
            cur_leg = internal_leg_prev
            if new_high:
                cur_leg = BEARISH_LEG
            elif new_low:
                cur_leg = BULLISH_LEG
            if cur_leg != internal_leg_prev:
                if cur_leg == BULLISH_LEG:
                    update_pivot_from_swing(internal_low, lows[in_target], times[in_target], in_target)
                else:
                    update_pivot_from_swing(internal_high, highs[in_target], times[in_target], in_target)
            internal_leg_prev = cur_leg

        # ---- EQH/EQL (size = eqhl_length) ----
        eq_target = i - eqhl_length
        atr_now = atr_series[i]
        if eq_target >= 0:
            right_high = max(highs[eq_target + 1 : i + 1])
            right_low = min(lows[eq_target + 1 : i + 1])
            new_high = highs[eq_target] > right_high
            new_low = lows[eq_target] < right_low
            if new_high:
                # 与上一个 eq_high 比较
                if eq_high.current_level is not None and abs(eq_high.current_level - highs[eq_target]) < eqhl_threshold * atr_now:
                    eqhs.insert(0, {
                        "level_a": eq_high.current_level,
                        "level_b": highs[eq_target],
                        "time_a": eq_high.bar_time,
                        "time_b": times[eq_target],
                    })
                update_pivot_from_swing(eq_high, highs[eq_target], times[eq_target], eq_target)
            elif new_low:
                if eq_low.current_level is not None and abs(eq_low.current_level - lows[eq_target]) < eqhl_threshold * atr_now:
                    eqls.insert(0, {
                        "level_a": eq_low.current_level,
                        "level_b": lows[eq_target],
                        "time_a": eq_low.bar_time,
                        "time_b": times[eq_target],
                    })
                update_pivot_from_swing(eq_low, lows[eq_target], times[eq_target], eq_target)

        # ---- BOS/CHoCH (swing 级别) ----
        # BOS (Break of Structure): 顺势突破前 swing 极值 → 趋势延续
        # CHoCH (Change of Character): 逆势突破前 swing 极值 → 趋势反转
        # 判定:close 从下方穿越 swing_high → bullish;从上方穿越 swing_low → bearish
        # 如果当前 bias 已经是 bullish,再次向上突破 = BOS;如果是 bearish 再向上突破 = CHoCH
        if (swing_high.current_level is not None and not swing_high.crossed
                and i > 0 and closes[i - 1] <= swing_high.current_level
                and closes[i] > swing_high.current_level):
            tag = "CHoCH" if swing_trend_bias == BEARISH else "BOS"
            swing_events.append({
                "type": tag, "side": "bullish",
                "broken_level": swing_high.current_level,
                "bar_time": times[i], "bar_index": i,
            })
            swing_high.crossed = True
            swing_trend_bias = BULLISH
            _store_ob(swing_obs, BULLISH, swing_high, parsed_highs, parsed_lows, times, i)
        if (swing_low.current_level is not None and not swing_low.crossed
                and i > 0 and closes[i - 1] >= swing_low.current_level
                and closes[i] < swing_low.current_level):
            tag = "CHoCH" if swing_trend_bias == BULLISH else "BOS"
            swing_events.append({
                "type": tag, "side": "bearish",
                "broken_level": swing_low.current_level,
                "bar_time": times[i], "bar_index": i,
            })
            swing_low.crossed = True
            swing_trend_bias = BEARISH
            _store_ob(swing_obs, BEARISH, swing_low, parsed_highs, parsed_lows, times, i)

        # ---- BOS/CHoCH (internal 级别) ----
        # 逻辑同 swing,但用 internal pivot(更短周期,更敏感)。
        # 额外条件:internal pivot 不能和 swing pivot 重合(避免重复信号)。
        if (internal_high.current_level is not None and not internal_high.crossed
                and internal_high.current_level != swing_high.current_level
                and i > 0 and closes[i - 1] <= internal_high.current_level
                and closes[i] > internal_high.current_level):
            tag = "CHoCH" if internal_trend_bias == BEARISH else "BOS"
            internal_events.append({
                "type": tag, "side": "bullish",
                "broken_level": internal_high.current_level,
                "bar_time": times[i], "bar_index": i,
            })
            internal_high.crossed = True
            internal_trend_bias = BULLISH
            _store_ob(internal_obs, BULLISH, internal_high, parsed_highs, parsed_lows, times, i)
        if (internal_low.current_level is not None and not internal_low.crossed
                and internal_low.current_level != swing_low.current_level
                and i > 0 and closes[i - 1] >= internal_low.current_level
                and closes[i] < internal_low.current_level):
            tag = "CHoCH" if internal_trend_bias == BULLISH else "BOS"
            internal_events.append({
                "type": tag, "side": "bearish",
                "broken_level": internal_low.current_level,
                "bar_time": times[i], "bar_index": i,
            })
            internal_low.crossed = True
            internal_trend_bias = BEARISH
            _store_ob(internal_obs, BEARISH, internal_low, parsed_highs, parsed_lows, times, i)

        # ---- FVG (Fair Value Gap,三根 K 线缺口) ----
        # Bullish FVG: bar[i].low > bar[i-2].high (向上跳空,中间 bar 是强阳)
        # Bearish FVG: bar[i].high < bar[i-2].low (向下跳空,中间 bar 是强阴)
        # 自适应阈值:中间 bar 的 body% 必须 > 历史平均 body% 的 2 倍(过滤噪声)
        if i >= 2:
            last_close = closes[i - 1]
            last_open = klines[i - 1]["open"]
            bar_delta_pct = (last_close - last_open) / (last_open * 100) if last_open else 0
            cum_abs_delta = 0.0
            for j in range(1, i + 1):
                o = klines[j - 1]["open"]
                c = closes[j - 1]
                if o:
                    cum_abs_delta += abs((c - o) / (o * 100))
            threshold = (cum_abs_delta / i * 2) if i > 0 else 0
            cur_high = highs[i]
            cur_low = lows[i]
            last2_high = highs[i - 2]
            last2_low = lows[i - 2]
            bullish_fvg = cur_low > last2_high and last_close > last2_high and bar_delta_pct > threshold
            bearish_fvg = cur_high < last2_low and last_close < last2_low and -bar_delta_pct > threshold
            if bullish_fvg:
                fvgs.insert(0, {
                    "bias": BULLISH,
                    "top": cur_low,
                    "bottom": last2_high,
                    "bar_time": times[i],
                })
            if bearish_fvg:
                fvgs.insert(0, {
                    "bias": BEARISH,
                    "top": last2_low,
                    "bottom": cur_high,
                    "bar_time": times[i],
                })

    # ===== 构造输出:把内部状态转为 JSON-friendly 的 dict =====
    last_idx = n - 1
    last_close = closes[last_idx]
    atr_now = atr_series[last_idx]

    def _last_event(events, current_bias):
        """取最近一次 BOS/CHoCH 事件,附加 bars_ago(距今多少根)。"""
        if not events:
            return None
        e = events[-1]
        return {
            "type": e["type"],
            "side": e["side"],
            "broken_level": e["broken_level"],
            "bars_ago": last_idx - e["bar_index"],
            "bar_time": e["bar_time"],
        }

    def _ob_view(ob):
        """把内部 OB dict 转为输出格式,附加 distance_pct(当前价距 OB 中心的百分比)。"""
        mid = (ob["bar_high"] + ob["bar_low"]) / 2
        dist_pct = (last_close - mid) / mid * 100 if mid else 0
        return {
            "bias": "bullish" if ob["bias"] == BULLISH else "bearish",
            "high": ob["bar_high"],
            "low": ob["bar_low"],
            "bar_time": ob["bar_time"],
            "age_bars": last_idx - ob["bar_index"],
            "distance_pct": round(dist_pct, 3),
        }

    def _fvg_view(fvg):
        """把内部 FVG dict 转为输出格式,附加 distance_pct。"""
        mid = (fvg["top"] + fvg["bottom"]) / 2
        dist_pct = (last_close - mid) / mid * 100 if mid else 0
        return {
            "bias": "bullish" if fvg["bias"] == BULLISH else "bearish",
            "top": fvg["top"],
            "bottom": fvg["bottom"],
            "bar_time": fvg["bar_time"],
            "distance_pct": round(dist_pct, 3),
        }

    # ===== Premium / Discount Zone =====
    # 基于 trailing 极值(实时最高/最低)划分区间:
    # - Premium: 价格在区间顶部 5% 以内(或 >52.5%)
    # - Discount: 价格在区间底部 5% 以内(或 <47.5%)
    # - Equilibrium: 47.5% ~ 52.5% 中间带
    span = trailing_top - trailing_bottom
    if span <= 0:
        zone = "equilibrium"
    else:
        pos = (last_close - trailing_bottom) / span
        if pos >= 0.95:
            zone = "premium"
        elif pos <= 0.05:
            zone = "discount"
        elif 0.475 <= pos <= 0.525:
            zone = "equilibrium"
        elif pos > 0.525:
            zone = "premium"
        else:
            zone = "discount"

    def _bias_str(b):
        """把内部 int 常量转为字符串。"""
        return "bullish" if b == BULLISH else "bearish" if b == BEARISH else "none"

    # ===== 最终输出 dict =====
    return {
        "_status": "ok",
        "n_bars": n,                    # 输入 K 线数量
        "current_price": last_close,    # 最新收盘价
        "atr": round(atr_now, 6),       # 当前 ATR 值
        "swing": {
            "trend_bias": _bias_str(swing_trend_bias),  # swing 级别趋势方向
            "last_event": _last_event(swing_events, swing_trend_bias),  # 最近 BOS/CHoCH
            "swing_high": {
                "level": swing_high.current_level,
                "bar_time": swing_high.bar_time,
                "crossed": swing_high.crossed,  # True=已被穿越,不会再触发
            } if swing_high.current_level is not None else None,
            "swing_low": {
                "level": swing_low.current_level,
                "bar_time": swing_low.bar_time,
                "crossed": swing_low.crossed,
            } if swing_low.current_level is not None else None,
            "trailing_top": trailing_top,           # 实时最高点
            "trailing_bottom": trailing_bottom,     # 实时最低点
            "trailing_top_time": trailing_top_time,
            "trailing_bottom_time": trailing_bottom_time,
            # strong/weak: bearish 趋势中 top 是 strong high(不容易被破)
            "strong_high": swing_trend_bias == BEARISH,
            "strong_low": swing_trend_bias == BULLISH,
        },
        "internal": {
            "trend_bias": _bias_str(internal_trend_bias),
            "last_event": _last_event(internal_events, internal_trend_bias),
        },
        "order_blocks": {
            "swing": [_ob_view(ob) for ob in swing_obs[:ob_max]],       # 最近 N 个未失效 swing OB
            "internal": [_ob_view(ob) for ob in internal_obs[:ob_max]], # 最近 N 个未失效 internal OB
        },
        "fvg": [_fvg_view(f) for f in fvgs[:fvg_max]],  # 最近 N 个未填补 FVG
        "equal_highs": eqhs[:5],    # 最近 5 对 Equal Highs(流动性磁铁)
        "equal_lows": eqls[:5],     # 最近 5 对 Equal Lows
        "zone": zone,               # 当前价位所在区域
        "zone_levels": {            # 各区域的具体价格阈值
            "trailing_top": trailing_top,
            "trailing_bottom": trailing_bottom,
            "premium_threshold": trailing_bottom + span * 0.95,
            "discount_threshold": trailing_bottom + span * 0.05,
            "equilibrium_low": trailing_bottom + span * 0.475,
            "equilibrium_high": trailing_bottom + span * 0.525,
        },
    }
