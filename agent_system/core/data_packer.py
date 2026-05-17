from datetime import datetime, timezone

def _parse_kline(raw):
    return {
        "open_time": raw[0],
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": raw[6],
        "quote_volume": float(raw[7]),
        "trades": raw[8],
        "taker_buy_volume": float(raw[9]),
        "taker_buy_quote_volume": float(raw[10]),
    }

def calc_atr(klines: list, period: int = 12) -> float:
    if len(klines) < 2:
        return 0.0
    trs = []
    for i in range(1, len(klines)):
        h = klines[i]["high"]
        l = klines[i]["low"]
        prev_c = klines[i-1]["close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    use = trs[-period:] if len(trs) > period else trs
    return sum(use) / len(use) if use else 0.0

def calc_bb_width(closes: list, period: int = 20, std_mult: float = 2.0) -> float:
    if len(closes) < period:
        return 0.0
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((c - mean) ** 2 for c in window) / period
    std = variance ** 0.5
    upper = mean + std_mult * std
    lower = mean - std_mult * std
    return (upper - lower) / mean if mean else 0.0

def calc_ema(closes: list, period: int) -> float:
    if not closes:
        return 0.0
    k = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema

def _bb_width_pct_rank(closes: list, period: int, lookback: int = 100) -> float:
    if len(closes) < period + lookback:
        return 50.0
    widths = []
    for i in range(lookback):
        end = len(closes) - i
        widths.append(calc_bb_width(closes[:end], period))
    current = widths[0]
    rank = sum(1 for w in widths if w <= current)
    return 100.0 * rank / len(widths)

def _extract_tags(pack: dict) -> list:
    tags = []
    funding_now = pack["funding"]["current"]
    if funding_now > 0.0010:
        tags.append("funding=extreme_high")
    elif funding_now < -0.0010:
        tags.append("funding=extreme_low")
    else:
        tags.append("funding=normal")

    top_pos = pack["positions"]["top_position_ratio_now"]
    if top_pos > 2.5:
        tags.append("smart_money=extreme_long")
    elif top_pos < 0.4:
        tags.append("smart_money=extreme_short")
    else:
        tags.append("smart_money=normal")

    bb_pct = pack["indicators"]["bb_width_pct"]
    if bb_pct < 25:
        tags.append("volatility=compressed")
    elif bb_pct > 75:
        tags.append("volatility=expanding")
    else:
        tags.append("volatility=normal")
    return tags

def build(symbol: str, binance, peer_symbols: list = None) -> dict:
    klines_raw = {
        "1h": binance.get_klines(symbol, interval="1h", limit=168),
        "4h": binance.get_klines(symbol, interval="4h", limit=180),
        "1d": binance.get_klines(symbol, interval="1d", limit=180),
        "1w": binance.get_klines(symbol, interval="1w", limit=104),
    }
    klines = {tf: [_parse_kline(r) for r in raw] for tf, raw in klines_raw.items()}

    funding_history = binance.get_funding_rate_history(symbol, limit=90)
    funding_info_all = binance.get_funding_info()
    finfo = next((f for f in funding_info_all if f.get("symbol") == symbol), {})
    funding_now = float(funding_history[-1]["fundingRate"]) if funding_history else 0.0

    oi = binance.get_open_interest_hist(symbol, period="1h", limit=180)
    top_pos = binance.get_top_long_short_position_ratio(symbol, period="1h", limit=180)
    top_acc = binance.get_top_long_short_account_ratio(symbol, period="1h", limit=180)
    global_acc = binance.get_global_long_short_account_ratio(symbol, period="1h", limit=180)

    klines_1h = klines["1h"]
    closes_1h = [k["close"] for k in klines_1h]
    closes_1d = [k["close"] for k in klines["1d"]]

    indicators = {
        "atr_12h": calc_atr(klines_1h[-12:], period=12),
        "atr_7d": calc_atr(klines["1d"][-7:], period=7),
        "bb_width_now": calc_bb_width(closes_1h, period=20),
        "bb_width_pct": _bb_width_pct_rank(closes_1h, period=20, lookback=100),
        "ema_20_1h": calc_ema(closes_1h, 20),
        "ema_50_1h": calc_ema(closes_1h, 50),
        "ema_200_1h": calc_ema(closes_1h, 200),
        "ema_20_1d": calc_ema(closes_1d, 20),
        "ema_50_1d": calc_ema(closes_1d, 50),
        "ema_200_1d": calc_ema(closes_1d, 200),
    }

    peer_funding = {}
    if peer_symbols:
        for ps in peer_symbols:
            try:
                pf = binance.get_premium_index(ps)
                peer_funding[ps] = float(pf.get("lastFundingRate", 0))
            except Exception:
                peer_funding[ps] = None

    pack = {
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "price_now": closes_1h[-1] if closes_1h else 0.0,
        "klines": klines,
        "funding": {
            "current": funding_now,
            "history_30d": funding_history[-90:] if funding_history else [],
            "cap": float(finfo.get("adjustedFundingRateCap", 0.02)) if finfo else 0.02,
            "floor": float(finfo.get("adjustedFundingRateFloor", -0.02)) if finfo else -0.02,
            "interval_hours": int(finfo.get("fundingIntervalHours", 8)) if finfo else 8,
        },
        "positions": {
            "oi_history": oi,
            "top_position_ratio_history": top_pos,
            "top_account_ratio_history": top_acc,
            "global_account_ratio_history": global_acc,
            "top_position_ratio_now": float(top_pos[-1]["longShortRatio"]) if top_pos else 1.0,
            "top_account_ratio_now": float(top_acc[-1]["longShortRatio"]) if top_acc else 1.0,
            "global_account_ratio_now": float(global_acc[-1]["longShortRatio"]) if global_acc else 1.0,
        },
        "volume": {
            "recent_24h": sum(k["quote_volume"] for k in klines_1h[-24:]),
            "ma_7d": sum(k["quote_volume"] for k in klines_1h[-168:]) / 7,
            "taker_buy_ratio_recent": (
                sum(k["taker_buy_quote_volume"] for k in klines_1h[-24:]) /
                sum(k["quote_volume"] for k in klines_1h[-24:])
                if klines_1h and sum(k["quote_volume"] for k in klines_1h[-24:]) > 0 else 0.5
            ),
        },
        "indicators": indicators,
        "peer_funding": peer_funding,
    }
    pack["tags"] = _extract_tags(pack)
    return pack
