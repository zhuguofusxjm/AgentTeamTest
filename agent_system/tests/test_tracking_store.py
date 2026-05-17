import json
from agent_system.data.db import init_new_tables
from agent_system.data.tracking_store import (
    add_tracked_position, get_active_tracks, close_tracked_position,
    save_track_snapshot, list_track_history,
)

def test_add_and_list_active(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tid = add_tracked_position(db, symbol="ETHUSDT", direction="多",
                                entry_price=3120, stop_loss=3050, take_profit=3260,
                                entry_signals="trend+smart_money")
    active = get_active_tracks(db)
    assert len(active) == 1
    assert active[0]["id"] == tid
    assert active[0]["status"] == "active"

def test_close(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tid = add_tracked_position(db, "ETHUSDT", "多", 3120, 3050, 3260, "")
    close_tracked_position(db, tid, reason="manual")
    active = get_active_tracks(db)
    assert len(active) == 0

def test_save_and_list_snapshots(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tid = add_tracked_position(db, "ETHUSDT", "多", 3120, 3050, 3260, "")
    save_track_snapshot(db, tid, snapshot={"price": 3150, "pnl": 0.96})
    save_track_snapshot(db, tid, snapshot={"price": 3170, "pnl": 1.6})
    rows = list_track_history(db, tid)
    assert len(rows) == 2
    # ORDER BY id DESC, latest first
    assert json.loads(rows[0]["snapshot_json"])["price"] == 3170
