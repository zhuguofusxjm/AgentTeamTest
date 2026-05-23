from unittest.mock import MagicMock
from agent_system.core.data_packer import build, calc_atr, calc_bb_width

def test_calc_atr_basic():
    klines = [
        {"high": 110, "low": 100, "close": 105},
        {"high": 112, "low": 103, "close": 108},
        {"high": 115, "low": 105, "close": 110},
    ]
    atr = calc_atr(klines, period=2)
    assert atr > 0

def test_calc_bb_width_basic():
    closes = [100, 101, 99, 100, 102, 98, 100, 101, 99, 100,
              102, 98, 100, 101, 99, 100, 102, 98, 100, 101]
    width = calc_bb_width(closes, period=20, std_mult=2)
    assert width > 0

def test_build_returns_required_fields():
    class FakeBinance:
        def get_klines(self, symbol, interval, limit, **kw):
            return [[i*1000, "100", "110", "95", "105", "1000", i*1000+1, "100000", 10, "500", "50000", "0"]
                    for i in range(200)]
        def get_funding_rate_history(self, symbol, limit, **kw):
            return [{"symbol": symbol, "fundingRate": "0.0001", "fundingTime": 1}]
        def get_funding_info(self):
            return [{"symbol": "ETHUSDT", "adjustedFundingRateCap": "0.02",
                     "adjustedFundingRateFloor": "-0.02", "fundingIntervalHours": 8}]
        def get_open_interest_hist(self, symbol, period, limit):
            return [{"symbol": symbol, "sumOpenInterest": "100", "sumOpenInterestValue": "1000", "timestamp": 1}]
        def get_top_long_short_position_ratio(self, symbol, period, limit):
            return [{"symbol": symbol, "longShortRatio": "1.5", "timestamp": 1}]
        def get_top_long_short_account_ratio(self, symbol, period, limit):
            return [{"symbol": symbol, "longShortRatio": "1.2", "timestamp": 1}]
        def get_global_long_short_account_ratio(self, symbol, period, limit):
            return [{"symbol": symbol, "longShortRatio": "0.9", "timestamp": 1}]
        def get_premium_index(self, symbol):
            return {"symbol": symbol, "lastFundingRate": "0.0002"}

    pack = build(symbol="ETHUSDT", binance=FakeBinance(), peer_symbols=["BTCUSDT"])
    assert pack["symbol"] == "ETHUSDT"
    assert "klines" in pack
    assert "1h" in pack["klines"]
    assert "4h" in pack["klines"]
    assert "1d" in pack["klines"]
    assert "1w" in pack["klines"]
    assert "funding" in pack
    assert "positions" in pack
    assert "indicators" in pack
    assert "atr_12h" in pack["indicators"]
    assert "tags" in pack
    assert isinstance(pack["tags"], list)
    assert "smc" in pack
    assert "4h" in pack["smc"]
    assert "1d" in pack["smc"]
