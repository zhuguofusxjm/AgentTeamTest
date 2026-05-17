import json
from agent_system.data.db import init_new_tables
from agent_system.data.decisions_store import save_decision, get_decision, list_open_decisions, update_decision_status, list_recent_decisions

def test_save_and_get(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"symbol": "ETHUSDT", "direction": "多", "entry_price": 3120,
            "stop_loss": 3050, "take_profit": 3260, "confidence": 65,
            "key_evidence": ["e"], "key_risks": ["r"]}
    did = save_decision(db, symbol="ETHUSDT", trigger_mode="chat",
                        card=card, tags=["funding=normal"], audit_path="tracks/x.json")
    got = get_decision(db, did)
    assert got["symbol"] == "ETHUSDT"
    assert got["status"] == "open"
    assert got["direction"] == "多"
    assert json.loads(got["tags"]) == ["funding=normal"]

def test_list_open(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 1, "stop_loss": 1, "take_profit": 1, "confidence": 50,
            "key_evidence": [], "key_risks": []}
    save_decision(db, "A", "chat", card, [], "p")
    save_decision(db, "B", "scan", card, [], "p")
    open_list = list_open_decisions(db)
    assert len(open_list) == 2

def test_update_status(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 1, "stop_loss": 1, "take_profit": 1, "confidence": 50,
            "key_evidence": [], "key_risks": []}
    did = save_decision(db, "A", "chat", card, [], "p")
    update_decision_status(db, did, status="win", realized_pnl_pct=5.2)
    got = get_decision(db, did)
    assert got["status"] == "win"
    assert got["realized_pnl_pct"] == 5.2

def test_list_recent(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 1, "stop_loss": 1, "take_profit": 1, "confidence": 50,
            "key_evidence": [], "key_risks": []}
    for i in range(5):
        save_decision(db, f"S{i}", "chat", card, [], "p")
    rows = list_recent_decisions(db, limit=3)
    assert len(rows) == 3
    # 按 decision_id DESC
    assert rows[0]["symbol"] == "S4"
