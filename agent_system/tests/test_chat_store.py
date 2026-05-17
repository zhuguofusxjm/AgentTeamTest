from agent_system.data.db import init_new_tables
from agent_system.data.chat_store import save_message, list_messages

def test_save_and_list(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    save_message(db, "sess-1", "user", "hi", decision_id=None)
    save_message(db, "sess-1", "assistant", "hello", decision_id=42)
    msgs = list_messages(db, "sess-1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["decision_id"] == 42

def test_messages_isolated_by_session(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    save_message(db, "s1", "user", "a")
    save_message(db, "s2", "user", "b")
    assert len(list_messages(db, "s1")) == 1
    assert len(list_messages(db, "s2")) == 1
    assert len(list_messages(db, "s3")) == 0
