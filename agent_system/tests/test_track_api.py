"""Tests for /api/track endpoint — converting a saved decision into an active track."""
import json
from unittest.mock import MagicMock
import pytest
from agent_system.data.db import init_new_tables
from agent_system.data.decisions_store import save_decision
from agent_system.data.tracking_store import get_active_tracks
from agent_system.web.app import create_app


@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    app = create_app(cfg={}, chat_runner=MagicMock(), audit_dir=str(tmp_path / "tracks"), db_path=db)
    app.testing = True
    return app.test_client(), db


def _save_card(db, symbol="ETHUSDT", direction="多"):
    return save_decision(db, symbol, "chat",
                          {"direction": direction, "entry_price": 100,
                           "stop_loss": 95, "take_profit": 110, "confidence": 70,
                           "key_evidence": [], "key_risks": [],
                           "execution_plan": "分批进场"},
                          ["funding=normal"], "")


def test_track_creates_position_from_decision(client):
    c, db = client
    did = _save_card(db, "ETHUSDT", "多")
    resp = c.post("/api/track", json={"decision_id": did})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["symbol"] == "ETHUSDT"
    assert data["direction"] == "多"
    assert isinstance(data["track_id"], int)

    tracks = get_active_tracks(db)
    assert len(tracks) == 1
    t = tracks[0]
    assert t["symbol"] == "ETHUSDT"
    assert t["direction"] == "多"
    assert t["entry_price"] == 100
    assert t["stop_loss"] == 95
    assert t["take_profit"] == 110
    assert t["entry_signals"] == f"decision_{did}"


def test_track_rejects_observation_decision(client):
    c, db = client
    did = _save_card(db, "ETHUSDT", "观望")
    resp = c.post("/api/track", json={"decision_id": did})
    assert resp.status_code == 400
    assert "观望" in resp.get_json()["error"]
    assert get_active_tracks(db) == []


def test_track_rejects_duplicate_active_symbol(client):
    c, db = client
    did1 = _save_card(db, "ETHUSDT", "多")
    c.post("/api/track", json={"decision_id": did1})

    did2 = _save_card(db, "ETHUSDT", "空")
    resp = c.post("/api/track", json={"decision_id": did2})
    assert resp.status_code == 409
    body = resp.get_json()
    assert "已有活跃跟踪" in body["error"]
    assert get_active_tracks(db)[0]["direction"] == "多"  # 原跟踪未被覆盖


def test_track_404_for_missing_decision(client):
    c, _ = client
    resp = c.post("/api/track", json={"decision_id": 99999})
    assert resp.status_code == 404


def test_track_400_when_no_decision_id(client):
    c, _ = client
    resp = c.post("/api/track", json={})
    assert resp.status_code == 400


def test_list_tracks_returns_active(client):
    c, db = client
    did = _save_card(db, "BTCUSDT", "空")
    c.post("/api/track", json={"decision_id": did})

    resp = c.get("/api/tracks")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["symbol"] == "BTCUSDT"
    assert data[0]["direction"] == "空"


def test_cancel_track_closes_active_position(client):
    c, db = client
    did = _save_card(db, "ETHUSDT", "多")
    res = c.post("/api/track", json={"decision_id": did})
    track_id = res.get_json()["track_id"]

    resp = c.delete(f"/api/tracks/{track_id}")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "closed"
    assert get_active_tracks(db) == []


def test_cancel_unknown_track_returns_404(client):
    c, _ = client
    resp = c.delete("/api/tracks/9999")
    assert resp.status_code == 404


def test_cancel_already_closed_returns_404(client):
    c, db = client
    did = _save_card(db, "ETHUSDT", "多")
    track_id = c.post("/api/track", json={"decision_id": did}).get_json()["track_id"]
    c.delete(f"/api/tracks/{track_id}")
    # 第二次再 delete 应当 404
    resp = c.delete(f"/api/tracks/{track_id}")
    assert resp.status_code == 404
