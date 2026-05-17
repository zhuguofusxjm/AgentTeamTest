from datetime import datetime
from agent_system.data.db import get_conn

def save_message(db_path, session_id, role, content, decision_id=None) -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO chat_messages (session_id, role, content, decision_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, role, content, decision_id, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def list_messages(db_path, session_id) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY msg_id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
