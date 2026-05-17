from datetime import datetime, timedelta
from unittest.mock import MagicMock
from agent_system.data.db import init_new_tables, get_conn
from agent_system.data.decisions_store import save_decision, get_decision
from agent_system.runners.decision_status_tracker import DecisionStatusTracker

def test_marks_win_when_price_hits_take_profit(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    binance = MagicMock()
    binance.get_klines.return_value = [
        [0, "100", "112", "99", "111", "1", 0, "1", 0, "1", "1", "0"],
    ]
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()
    got = get_decision(db, did)
    assert got["status"] == "win"
    assert got["realized_pnl_pct"] is not None and got["realized_pnl_pct"] > 0

def test_marks_loss_when_price_hits_stop_loss(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    binance = MagicMock()
    binance.get_klines.return_value = [
        [0, "100", "100", "94", "94", "1", 0, "1", 0, "1", "1", "0"],
    ]
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()
    got = get_decision(db, did)
    assert got["status"] == "loss"
    assert got["realized_pnl_pct"] < 0

def test_kline_window_anchored_to_created_at(tmp_path):
    """状态追踪只看决策创建后的价格,避免历史价格误判。"""
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    captured = {}
    def fake_get_klines(symbol, interval, limit, start_time=None, end_time=None, **kw):
        captured["start_time"] = start_time
        captured["interval"] = interval
        return [[0, "100", "102", "99", "101", "1", 0, "1", 0, "1", "1", "0"]]

    binance = MagicMock()
    binance.get_klines.side_effect = fake_get_klines
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()

    got = get_decision(db, did)
    created_ms = int(datetime.fromisoformat(got["created_at"]).timestamp() * 1000)
    assert captured["start_time"] is not None
    assert abs(captured["start_time"] - created_ms) < 60_000


def test_marks_expired_after_timeout(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    conn = get_conn(db)
    eight_days_ago = (datetime.now() - timedelta(days=8)).isoformat()
    conn.execute("UPDATE decisions SET created_at = ? WHERE decision_id = ?", (eight_days_ago, did))
    conn.commit(); conn.close()

    binance = MagicMock()
    binance.get_klines.return_value = [
        [0, "100", "102", "98", "101", "1", 0, "1", 0, "1", "1", "0"],
    ]
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()
    got = get_decision(db, did)
    assert got["status"] == "expired"
