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
    assert "BUSDT" in candidates  # 极端费率
    assert "CUSDT" in candidates  # 极端多空比
    assert "DUSDT" not in candidates  # 体量太小
