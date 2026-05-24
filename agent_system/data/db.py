import sqlite3

def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

DDL_DECISIONS = """
CREATE TABLE IF NOT EXISTS decisions (
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  trigger_mode TEXT,
  direction TEXT,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  confidence INTEGER,
  tags TEXT,
  card_json TEXT,
  audit_path TEXT,
  status TEXT,
  closed_at TEXT,
  realized_pnl_pct REAL,
  created_at TEXT
)
"""
DDL_DECISIONS_IDX_SYMBOL = "CREATE INDEX IF NOT EXISTS idx_dec_symbol ON decisions(symbol)"
DDL_DECISIONS_IDX_STATUS = "CREATE INDEX IF NOT EXISTS idx_dec_status ON decisions(status)"
DDL_MIGRATE_PREFILTER_TAGS = """
ALTER TABLE decisions ADD COLUMN prefilter_tags TEXT
"""

DDL_EXPERIENCES = """
CREATE TABLE IF NOT EXISTS experiences (
  experience_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tags TEXT,
  scenario_summary TEXT,
  decisions_referenced TEXT,
  outcome_stats TEXT,
  lesson TEXT,
  applicable_when TEXT,
  caveats TEXT,
  created_at TEXT,
  updated_at TEXT
)
"""
DDL_EXPERIENCES_IDX = "CREATE INDEX IF NOT EXISTS idx_exp_updated ON experiences(updated_at)"

DDL_CHAT_MESSAGES = """
CREATE TABLE IF NOT EXISTS chat_messages (
  msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  role TEXT,
  content TEXT,
  decision_id INTEGER,
  created_at TEXT
)
"""
DDL_CHAT_IDX = "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id)"

DDL_TRACKED_POSITIONS = """
CREATE TABLE IF NOT EXISTS tracked_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  direction TEXT,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  status TEXT,
  created_at TEXT,
  closed_at TEXT,
  close_reason TEXT,
  notes TEXT,
  entry_signals TEXT
)
"""
DDL_TRACKED_IDX = "CREATE INDEX IF NOT EXISTS idx_track_status ON tracked_positions(status)"

DDL_TRACK_HISTORY = """
CREATE TABLE IF NOT EXISTS track_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  track_id INTEGER,
  snapshot_json TEXT,
  created_at TEXT
)
"""
DDL_TRACK_HISTORY_IDX = "CREATE INDEX IF NOT EXISTS idx_th_track ON track_history(track_id)"

def init_new_tables(db_path: str):
    conn = get_conn(db_path)
    try:
        conn.execute(DDL_DECISIONS)
        conn.execute(DDL_DECISIONS_IDX_SYMBOL)
        conn.execute(DDL_DECISIONS_IDX_STATUS)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()}
        if "prefilter_tags" not in existing:
            conn.execute(DDL_MIGRATE_PREFILTER_TAGS)
        conn.execute(DDL_EXPERIENCES)
        conn.execute(DDL_EXPERIENCES_IDX)
        conn.execute(DDL_CHAT_MESSAGES)
        conn.execute(DDL_CHAT_IDX)
        conn.execute(DDL_TRACKED_POSITIONS)
        conn.execute(DDL_TRACKED_IDX)
        conn.execute(DDL_TRACK_HISTORY)
        conn.execute(DDL_TRACK_HISTORY_IDX)
        conn.commit()
    finally:
        conn.close()
