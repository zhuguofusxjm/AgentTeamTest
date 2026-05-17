"""Per-decision execution metrics for retrospective analysis.

Computes how the price moved between entry and close:
- mfe_pct: Maximum Favorable Excursion (best you could have closed)
- mae_pct: Maximum Adverse Excursion (worst drawdown you'd have endured)
- time_to_close_hours
- path_shape: "direct" / "v_reversal" / "false_breakout" / "choppy" / "unknown"

These feed back into retro prompts so the LLM can spot patterns like
"止损设得太紧" (large MFE but stopped out at small MAE first) or
"假突破假信号" (price briefly touched TP then reversed past entry).
"""
from datetime import datetime


def _classify_path(direction: str, entry: float, sl: float, tp: float,
                   highs: list, lows: list, final_close: float) -> str:
    if not highs or not lows:
        return "unknown"

    if direction == "多":
        first_extreme_idx_up = next((i for i, h in enumerate(highs) if h >= tp), None)
        first_extreme_idx_dn = next((i for i, l in enumerate(lows) if l <= sl), None)
        # 起点附近 (前 25% 时间) 是否就反向跌过
        early_cut = len(lows) // 4 or 1
        early_low = min(lows[:early_cut]) if early_cut else lows[0]
        early_drawdown_pct = (entry - early_low) / entry * 100
        sl_distance_pct = (entry - sl) / entry * 100
        if first_extreme_idx_up is not None and early_drawdown_pct < sl_distance_pct * 0.4:
            return "direct"
        if first_extreme_idx_up is not None and early_drawdown_pct >= sl_distance_pct * 0.6:
            return "v_reversal"
        if max(highs) >= tp and final_close < entry:
            return "false_breakout"
        return "choppy"
    else:
        first_extreme_idx_dn = next((i for i, l in enumerate(lows) if l <= tp), None)
        early_cut = len(highs) // 4 or 1
        early_high = max(highs[:early_cut]) if early_cut else highs[0]
        early_drawup_pct = (early_high - entry) / entry * 100
        sl_distance_pct = (sl - entry) / entry * 100
        if first_extreme_idx_dn is not None and early_drawup_pct < sl_distance_pct * 0.4:
            return "direct"
        if first_extreme_idx_dn is not None and early_drawup_pct >= sl_distance_pct * 0.6:
            return "v_reversal"
        if min(lows) <= tp and final_close > entry:
            return "false_breakout"
        return "choppy"


def compute_execution_metrics(decision: dict, binance) -> dict:
    direction = decision.get("direction")
    entry = decision.get("entry_price")
    sl = decision.get("stop_loss")
    tp = decision.get("take_profit")
    created_at = decision.get("created_at")
    closed_at = decision.get("closed_at")

    if not all([direction in ("多", "空"), entry, sl, tp, created_at]):
        return {"mfe_pct": None, "mae_pct": None, "time_to_close_hours": None,
                "path_shape": "unknown"}

    created = datetime.fromisoformat(created_at)
    closed = datetime.fromisoformat(closed_at) if closed_at else datetime.now()
    start_ms = int(created.timestamp() * 1000)
    end_ms = int(closed.timestamp() * 1000)

    try:
        klines = binance.get_klines(decision["symbol"], interval="1h", limit=500,
                                     start_time=start_ms, end_time=end_ms)
    except Exception:
        klines = []

    if not klines:
        return {"mfe_pct": None, "mae_pct": None,
                "time_to_close_hours": int((closed - created).total_seconds() // 3600),
                "path_shape": "unknown"}

    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    final_close = float(klines[-1][4])

    if direction == "多":
        mfe_pct = (max(highs) - entry) / entry * 100
        mae_pct = (entry - min(lows)) / entry * 100
    else:
        mfe_pct = (entry - min(lows)) / entry * 100
        mae_pct = (max(highs) - entry) / entry * 100

    return {
        "mfe_pct": round(mfe_pct, 2),
        "mae_pct": round(mae_pct, 2),
        "time_to_close_hours": int((closed - created).total_seconds() // 3600),
        "path_shape": _classify_path(direction, entry, sl, tp, highs, lows, final_close),
    }
