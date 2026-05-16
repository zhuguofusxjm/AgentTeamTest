import json
import os
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
