import json
from datetime import datetime
from agent_system.data.db import get_conn

def add_tracked_position(db_path, symbol, direction, entry_price,
                          stop_loss, take_profit, entry_signals="", notes="") -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO tracked_positions
               (symbol, direction, entry_price, stop_loss, take_profit,
                status, created_at, entry_signals, notes)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (symbol, direction, entry_price, stop_loss, take_profit,
             datetime.now().isoformat(), entry_signals, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_active_tracks(db_path) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tracked_positions WHERE status = 'active'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def close_tracked_position(db_path, track_id, reason: str = ""):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """UPDATE tracked_positions
               SET status = 'closed', closed_at = ?, close_reason = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), reason, track_id),
        )
        conn.commit()
    finally:
        conn.close()

def save_track_snapshot(db_path, track_id, snapshot: dict):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """INSERT INTO track_history (track_id, snapshot_json, created_at)
               VALUES (?, ?, ?)""",
            (track_id, json.dumps(snapshot, ensure_ascii=False, default=str),
             datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

def list_track_history(db_path, track_id, limit=50) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM track_history WHERE track_id = ?
               ORDER BY id DESC LIMIT ?""",
            (track_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
