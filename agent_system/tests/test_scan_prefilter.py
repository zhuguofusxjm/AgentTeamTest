from unittest.mock import MagicMock
from agent_system.runners.scan_runner import _prefilter_by_volume_and_extremes

def test_prefilter_combines_top_volume_funding_and_position():
    binance = MagicMock()
    binance.get_premium_index.return_value = [
        {"symbol": "AUSDT", "lastFundingRate": "0.0001"},
        {"symbol": "BUSDT", "lastFundingRate": "0.005"},
        {"symbol": "CUSDT", "lastFundingRate": "0.0002"},
        {"symbol": "EUSDT", "lastFundingRate": "0.0001"},
    ]
    def fake_ticker():
        return [
            {"symbol": "AUSDT", "quoteVolume": "1000000000"},
            {"symbol": "BUSDT", "quoteVolume": "500000000"},
            {"symbol": "CUSDT", "quoteVolume": "400000000"},
            {"symbol": "EUSDT", "quoteVolume": "300000000"},
            {"symbol": "DUSDT", "quoteVolume": "100"},
        ]
    binance.get_24h_ticker = fake_ticker
    def fake_top_pos(symbol, **kw):
        if symbol == "CUSDT":
            return [{"longShortRatio": "3.5", "timestamp": 1}]
        return [{"longShortRatio": "1.05", "timestamp": 1}]
    binance.get_top_long_short_position_ratio.side_effect = fake_top_pos

    candidates = _prefilter_by_volume_and_extremes(
        binance=binance, top_volume=4, top_funding=2, top_position_dev=2,
    )
    assert isinstance(candidates, list)
    symbols = [c["symbol"] for c in candidates]
    assert "BUSDT" in symbols  # 极端费率
    assert "CUSDT" in symbols  # 极端多空比
    assert "DUSDT" not in symbols  # 体量太小

    busdt = next(c for c in candidates if c["symbol"] == "BUSDT")
    assert "funding" in busdt["dims"]
    cusdt = next(c for c in candidates if c["symbol"] == "CUSDT")
    assert "position" in cusdt["dims"]


def test_prefilter_picks_price_momentum_oi_growth_and_volume_anomaly():
    """新增维度: 涨跌幅 / OI 增长率 / 成交量异动 各自能挑出极端者."""
    binance = MagicMock()

    def fake_ticker():
        return [
            # AUSDT 体量最大但其他都平淡
            {"symbol": "AUSDT", "quoteVolume": "1000000000", "priceChangePercent": "0.5"},
            # BUSDT 涨幅暴拉(动量极端)
            {"symbol": "BUSDT", "quoteVolume": "500000000", "priceChangePercent": "25.0"},
            # CUSDT 平淡(待会儿测 OI 增长)
            {"symbol": "CUSDT", "quoteVolume": "400000000", "priceChangePercent": "0.2"},
            # EUSDT 平淡(待会儿测成交量异动)
            {"symbol": "EUSDT", "quoteVolume": "300000000", "priceChangePercent": "0.1"},
        ]
    binance.get_24h_ticker = fake_ticker
    binance.get_premium_index.return_value = []  # 无费率极端
    binance.get_top_long_short_position_ratio.return_value = [{"longShortRatio": "1.0"}]

    # OI 增长率: 只有 CUSDT 有大幅增长
    def fake_oi(symbol, **kw):
        if symbol == "CUSDT":
            return [{"sumOpenInterest": "100"}] + [{"sumOpenInterest": "200"}] * 24
        return [{"sumOpenInterest": "100"}] * 25  # 无变化
    binance.get_open_interest_hist.side_effect = fake_oi

    # 成交量异动: 只有 EUSDT 异动 (24h vol 是均值的 5 倍)
    def fake_klines(symbol, interval, limit, **kw):
        # K 线: [t, o, h, l, c, vol, ct, quote_vol, ...]
        if symbol == "EUSDT":
            return [[0, 0, 0, 0, 0, 0, 0, "1000000", 0, 0, 0, 0]] * 7 + \
                   [[0, 0, 0, 0, 0, 0, 0, "5000000", 0, 0, 0, 0]]
        return [[0, 0, 0, 0, 0, 0, 0, "1000000", 0, 0, 0, 0]] * 8  # 无异动
    binance.get_klines.side_effect = fake_klines

    candidates = _prefilter_by_volume_and_extremes(
        binance=binance, top_volume=4,
        top_funding=2, top_position_dev=2,
        top_price_change=2, top_oi_growth=2, top_volume_anomaly=2,
    )

    assert isinstance(candidates, list)
    symbols = [c["symbol"] for c in candidates]
    assert "BUSDT" in symbols  # 涨幅极端
    assert "CUSDT" in symbols  # OI 增长极端
    assert "EUSDT" in symbols  # 成交量异动极端

    busdt = next(c for c in candidates if c["symbol"] == "BUSDT")
    assert "price" in busdt["dims"]
    cusdt = next(c for c in candidates if c["symbol"] == "CUSDT")
    assert "oi_growth" in cusdt["dims"]
    eusdt = next(c for c in candidates if c["symbol"] == "EUSDT")
    assert "volume_anomaly" in eusdt["dims"]

