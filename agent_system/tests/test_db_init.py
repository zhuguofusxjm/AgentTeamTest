import sqlite3
from agent_system.data.db import get_conn, init_new_tables

def test_init_creates_decisions_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='decisions'")
        assert cur.fetchone() is not None
    finally:
        conn.close()

def test_init_creates_experiences_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='experiences'")
        assert cur.fetchone() is not None
    finally:
        conn.close()

def test_init_creates_chat_messages_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'")
        assert cur.fetchone() is not None
    finally:
        conn.close()

def test_init_creates_tracked_positions_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_positions'")
        assert cur.fetchone() is not None
    finally:
        conn.close()

def test_init_creates_track_history_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='track_history'")
        assert cur.fetchone() is not None
    finally:
        conn.close()

def test_init_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    init_new_tables(db_path)  # 不应报错
