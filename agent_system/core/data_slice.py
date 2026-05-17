"""Helpers for slicing the DataPack into per-Mate views.

Each Mate only needs a subset of the full DataPack. Sending the whole pack
(~120K tokens) to every Mate is wasteful — slicing brings each Mate's
prompt down to 5-20K tokens, an ~80% reduction.

Use these helpers from a Mate's `select_fields` override.
"""


def keep(data_pack: dict, paths: list) -> dict:
    """Return a shallow dict containing only the listed top-level keys.

    Always retains symbol/timestamp/price_now/tags as context anchors.
    """
    base_keys = {"symbol", "timestamp", "price_now", "tags"}
    out = {k: data_pack[k] for k in base_keys if k in data_pack}
    for p in paths:
        if p in data_pack:
            out[p] = data_pack[p]
    return out


def slim_klines(klines_by_tf: dict, last_n: dict) -> dict:
    """Trim each timeframe's klines to its last_n entries.

    last_n: {"1h": 24, "4h": 30, ...}
    timeframes not in last_n are dropped entirely.
    """
    out = {}
    for tf, n in last_n.items():
        rows = klines_by_tf.get(tf) or []
        if n is None or n >= len(rows):
            out[tf] = rows
        else:
            out[tf] = rows[-n:]
    return out


def kline_summary(klines: list) -> dict:
    """Reduce a list of klines to high/low/first_close/last_close + count.

    Useful when a Mate only needs context on the longer timeframe.
    """
    if not klines:
        return {"count": 0}
    highs = [k.get("high", 0) for k in klines]
    lows = [k.get("low", 0) for k in klines]
    return {
        "count": len(klines),
        "first_close": klines[0].get("close"),
        "last_close": klines[-1].get("close"),
        "highest": max(highs) if highs else None,
        "lowest": min(lows) if lows else None,
    }


def trim_history(rows: list, last_n: int) -> list:
    if not rows:
        return rows
    return rows[-last_n:]
