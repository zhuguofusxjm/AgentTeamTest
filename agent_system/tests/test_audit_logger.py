import json
import os
from pathlib import Path
from agent_system.core.audit_logger import AuditLogger

def test_audit_log_call_creates_file(tmp_path):
    logger = AuditLogger(audit_dir=str(tmp_path))
    audit_id = logger.start_session(prefix="decision", session_key="42")
    logger.log_call(
        audit_id=audit_id,
        round_num=1,
        mate="trend_multi_tf",
        model="deepseek-chat",
        prompt="test prompt",
        response="test response",
        tokens={"prompt": 10, "completion": 20, "total": 30},
        duration_ms=1000,
    )
    logger.finalize(audit_id, final_card={"direction": "多"})

    files = list(tmp_path.glob("decision_42.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["session_key"] == "42"
    assert len(data["rounds"][0]["calls"]) == 1
    assert data["final_card"]["direction"] == "多"

def test_log_call_groups_by_round(tmp_path):
    logger = AuditLogger(audit_dir=str(tmp_path))
    aid = logger.start_session(prefix="decision", session_key="1")
    logger.log_call(aid, 1, "m1", "deepseek-chat", "p", "r", {"total": 1}, 100)
    logger.log_call(aid, 1, "m2", "deepseek-chat", "p", "r", {"total": 1}, 100)
    logger.log_call(aid, 2, "m3", "deepseek-chat", "p", "r", {"total": 1}, 100)
    logger.finalize(aid, final_card={})
    data = json.loads((tmp_path / "decision_1.json").read_text(encoding="utf-8"))
    assert len(data["rounds"]) == 2
    assert len(data["rounds"][0]["calls"]) == 2
    assert len(data["rounds"][1]["calls"]) == 1

import pytest

def test_unknown_audit_id_raises(tmp_path):
    logger = AuditLogger(audit_dir=str(tmp_path))
    with pytest.raises(ValueError):
        logger.log_call("ghost", 1, "m", "model", "p", "r", {}, 0)
    with pytest.raises(ValueError):
        logger.finalize("ghost", final_card={})

def test_path_injection_sanitized(tmp_path):
    logger = AuditLogger(audit_dir=str(tmp_path))
    aid = logger.start_session(prefix="decision", session_key="../../evil")
    logger.log_call(aid, 1, "m", "x", "p", "r", {}, 0)
    path = logger.finalize(aid, final_card={})
    # 文件应在 tmp_path 下,不能逃逸
    assert str(tmp_path) in path
    assert ".." not in Path(path).name

def test_concurrent_log_calls(tmp_path):
    import threading
    logger = AuditLogger(audit_dir=str(tmp_path))
    aid = logger.start_session(prefix="decision", session_key="concurrent")
    def worker(i):
        logger.log_call(aid, 1, f"m{i}", "x", "p", "r", {"total": 1}, 1)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    logger.finalize(aid, final_card={})
    data = json.loads((tmp_path / "decision_concurrent.json").read_text(encoding="utf-8"))
    assert len(data["rounds"][0]["calls"]) == 20
