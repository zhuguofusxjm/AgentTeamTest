import json
from datetime import datetime
from agent_system.data.db import get_conn

def save_decision(db_path, symbol, trigger_mode, card, tags, audit_path) -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO decisions (symbol, trigger_mode, direction, entry_price,
               stop_loss, take_profit, confidence, tags, card_json, audit_path,
               status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (symbol, trigger_mode, card.get("direction"),
             card.get("entry_price"), card.get("stop_loss"), card.get("take_profit"),
             card.get("confidence"), json.dumps(tags, ensure_ascii=False),
             json.dumps(card, ensure_ascii=False), audit_path,
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_decision(db_path, decision_id) -> dict:
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def list_open_decisions(db_path) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM decisions WHERE status = 'open'").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_decision_status(db_path, decision_id, status, realized_pnl_pct=None):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """UPDATE decisions SET status = ?, closed_at = ?, realized_pnl_pct = ?
               WHERE decision_id = ?""",
            (status, datetime.now().isoformat(), realized_pnl_pct, decision_id),
        )
        conn.commit()
    finally:
        conn.close()

def list_recent_decisions(db_path, limit=50) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY decision_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
