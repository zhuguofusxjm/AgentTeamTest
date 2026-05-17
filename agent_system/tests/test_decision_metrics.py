from datetime import datetime, timedelta
from unittest.mock import MagicMock
from agent_system.core.decision_metrics import compute_execution_metrics


def _kline(open_ms, o, h, l, c):
    return [open_ms, str(o), str(h), str(l), str(c), "1", open_ms + 3600_000, "1", 0, "1", "1", "0"]


def test_long_direct_to_tp_metrics():
    """多头直接打到止盈,MFE 大,MAE 小,直奔形态。"""
    created = datetime.now() - timedelta(hours=4)
    decision = {
        "symbol": "ETHUSDT", "direction": "多",
        "entry_price": 100, "stop_loss": 95, "take_profit": 110,
        "created_at": created.isoformat(),
        "closed_at": (created + timedelta(hours=3)).isoformat(),
        "status": "win",
    }
    base_ms = int(created.timestamp() * 1000)
    klines = [
        _kline(base_ms, 100, 102, 99.5, 101),
        _kline(base_ms + 3600_000, 101, 105, 100.5, 104),
        _kline(base_ms + 7200_000, 104, 111, 103.5, 110.5),
    ]
    binance = MagicMock()
    binance.get_klines.return_value = klines

    m = compute_execution_metrics(decision, binance)
    assert m["mfe_pct"] >= 10  # 价格触达 111
    assert m["mae_pct"] <= 1   # 最低 99.5
    assert m["time_to_close_hours"] == 3
    assert m["path_shape"] == "direct"


def test_long_v_reversal_metrics():
    """多头先跌到接近止损再反弹打止盈。"""
    created = datetime.now() - timedelta(hours=10)
    decision = {
        "symbol": "ETHUSDT", "direction": "多",
        "entry_price": 100, "stop_loss": 95, "take_profit": 110,
        "created_at": created.isoformat(),
        "closed_at": (created + timedelta(hours=8)).isoformat(),
        "status": "win",
    }
    base_ms = int(created.timestamp() * 1000)
    klines = [
        _kline(base_ms, 100, 100.5, 96, 96.5),
        _kline(base_ms + 3600_000, 96.5, 97, 95.5, 96),
        _kline(base_ms + 7200_000, 96, 100, 95.8, 100),
        _kline(base_ms + 10800_000, 100, 110.2, 99, 110),
    ]
    binance = MagicMock()
    binance.get_klines.return_value = klines

    m = compute_execution_metrics(decision, binance)
    assert m["mfe_pct"] >= 10
    assert m["mae_pct"] >= 4   # 最低 95.5,跌幅 4.5%
    assert m["path_shape"] == "v_reversal"


def test_short_loss_metrics():
    """空头被止损打掉。"""
    created = datetime.now() - timedelta(hours=3)
    decision = {
        "symbol": "ETHUSDT", "direction": "空",
        "entry_price": 100, "stop_loss": 105, "take_profit": 90,
        "created_at": created.isoformat(),
        "closed_at": (created + timedelta(hours=2)).isoformat(),
        "status": "loss",
    }
    base_ms = int(created.timestamp() * 1000)
    klines = [
        _kline(base_ms, 100, 102, 99, 101),
        _kline(base_ms + 3600_000, 101, 106, 100.5, 105.5),
    ]
    binance = MagicMock()
    binance.get_klines.return_value = klines

    m = compute_execution_metrics(decision, binance)
    assert m["mfe_pct"] >= 0   # 空头 MFE = (entry - lowest)/entry
    assert m["mae_pct"] >= 5   # (highest - entry)/entry = 6
    assert m["time_to_close_hours"] == 2


def test_handles_missing_klines():
    decision = {
        "symbol": "ETHUSDT", "direction": "多",
        "entry_price": 100, "stop_loss": 95, "take_profit": 110,
        "created_at": datetime.now().isoformat(),
        "closed_at": datetime.now().isoformat(),
        "status": "expired",
    }
    binance = MagicMock()
    binance.get_klines.return_value = []
    m = compute_execution_metrics(decision, binance)
    assert m["mfe_pct"] is None
    assert m["mae_pct"] is None
    assert m["path_shape"] == "unknown"
