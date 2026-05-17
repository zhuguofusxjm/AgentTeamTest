import pytest
from unittest.mock import MagicMock
from agent_system.core.orchestrator import Orchestrator

def _mock_mate(name, view="多", confidence=70):
    m = MagicMock()
    m.name = name
    m.run.return_value = {"mate": name, "view": view, "confidence": confidence,
                          "evidence": ["e"], "extra": {}}
    return m

def test_round_1_calls_all_enabled_mates():
    cfg = {
        "modes": {"full": {"enabled_mates": ["m1", "m2", "position_mgr"], "rounds": 3}},
        "mates": {
            "m1": {"enabled": True, "model": "deepseek-chat"},
            "m2": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    mates = {"m1": _mock_mate("m1"), "m2": _mock_mate("m2"),
             "position_mgr": _mock_mate("position_mgr")}
    red_team = _mock_mate("red_team", view="空", confidence=60)
    red_team.run_rebuttal = MagicMock(return_value={"mate": "red_team", "view": "空", "extra": {}})
    decision_lead = MagicMock()
    decision_lead.synthesize.return_value = {"direction": "多", "confidence": 65}

    audit = MagicMock()
    audit.start_session.return_value = "audit-1"
    llm = MagicMock()
    from agent_system.providers.base import LLMResponse
    llm.chat.return_value = LLMResponse(text='{"keeps_view":true,"updated_confidence":70,"note":"x"}',
                                         usage={"total_tokens": 1}, model="deepseek-chat", raw={})
    orch = Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=red_team,
                        decision_lead=decision_lead, audit_logger=audit)
    pack = {"symbol": "ETHUSDT", "tags": []}
    card = orch.run(symbol="ETHUSDT", mode="full", data_pack=pack)

    assert mates["m1"].run.called
    assert mates["m2"].run.called
    assert mates["position_mgr"].run.called
    assert decision_lead.synthesize.called
    assert card["direction"] == "多"

def test_position_mgr_runs_after_other_mates():
    """position_mgr 必须在其他 Mate 完成后才能拿到 round_1_reports"""
    call_order = []
    def m_run(name):
        def _run(*args, **kwargs):
            call_order.append(name)
            return {"mate": name, "view": "多", "confidence": 70, "evidence": [], "extra": {}}
        return _run

    cfg = {
        "modes": {"full": {"enabled_mates": ["m1", "position_mgr"], "rounds": 3}},
        "mates": {
            "m1": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    m1 = MagicMock(); m1.run.side_effect = m_run("m1")
    pm = MagicMock(); pm.run.side_effect = m_run("position_mgr")
    rt = MagicMock(); rt.run_rebuttal = MagicMock(return_value={"mate":"red_team", "extra":{}})
    rt.run = MagicMock(return_value={"mate":"red_team","view":"观望","confidence":0,"evidence":[],"extra":{}})
    dl = MagicMock(); dl.synthesize.return_value = {"direction": "多"}
    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    from agent_system.providers.base import LLMResponse
    llm.chat.return_value = LLMResponse(text='{"keeps_view":true}', usage={}, model="x", raw={})

    orch = Orchestrator(cfg=cfg, llm_client=llm, mates={"m1": m1, "position_mgr": pm},
                        red_team=rt, decision_lead=dl, audit_logger=audit)
    orch.run(symbol="ETHUSDT", mode="full", data_pack={"symbol": "ETHUSDT", "tags": []})
    assert call_order.index("m1") < call_order.index("position_mgr")

def test_lean_mode_skips_round_2():
    cfg = {
        "modes": {"lean": {"enabled_mates": ["m1"], "rounds": 2}},
        "mates": {"m1": {"enabled": True, "model": "deepseek-chat"}},
        "default_model": "deepseek-chat",
    }
    m1 = _mock_mate("m1")
    rt = MagicMock()
    rt.run = MagicMock(return_value={"mate":"red_team","view":"观望","confidence":0,"evidence":[],"extra":{}})
    rt.run_rebuttal = MagicMock()
    dl = MagicMock()
    dl.synthesize.return_value = {"direction": "多"}
    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    orch = Orchestrator(cfg=cfg, llm_client=llm, mates={"m1": m1},
                        red_team=rt, decision_lead=dl, audit_logger=audit)
    orch.run(symbol="X", mode="lean", data_pack={"symbol": "X", "tags": []})
    rt.run_rebuttal.assert_not_called()
    assert audit.finalize.called


def test_emits_events_for_each_mate_and_phase():
    """orchestrator 通过 on_event 把每 Mate 的输出和阶段进度推给前端"""
    cfg = {
        "modes": {"full": {"enabled_mates": ["m1", "m2", "position_mgr"], "rounds": 3}},
        "mates": {
            "m1": {"enabled": True, "model": "deepseek-chat"},
            "m2": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    mates = {"m1": _mock_mate("m1", view="多", confidence=70),
             "m2": _mock_mate("m2", view="多", confidence=80),
             "position_mgr": _mock_mate("position_mgr", view="多", confidence=65)}
    rt = _mock_mate("red_team", view="空", confidence=55)
    rt.run_rebuttal = MagicMock(return_value={"mate":"red_team","view":"空",
                                                "extra":{"rebuttal":"反驳"}})
    dl = MagicMock(); dl.synthesize.return_value = {"direction": "多", "confidence": 65}
    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    from agent_system.providers.base import LLMResponse
    llm.chat.return_value = LLMResponse(
        text='{"mate":"m2","keeps_view":true,"updated_view":"多","updated_confidence":75,"note":"维持"}',
        usage={"total_tokens": 1}, model="deepseek-chat", raw={})

    events = []
    def on_event(name, payload):
        events.append((name, payload))

    orch = Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=rt,
                        decision_lead=dl, audit_logger=audit)
    orch.run(symbol="ETHUSDT", mode="full",
             data_pack={"symbol": "ETHUSDT", "tags": []}, on_event=on_event)

    names = [n for n, _ in events]
    # round 1: 每个 mate(包括 red_team / position_mgr)各一条 mate_done
    assert names.count("mate_done") >= 4   # m1,m2,red_team,position_mgr
    # round 2: rebuttal_start, rebuttal_done, response_done x N
    assert "rebuttal_done" in names
    assert names.count("response_done") >= 1
    # round 3
    assert "round_3_start" in names

    # 每个 mate_done 都应携带 mate 名 + view + confidence + 完整 result
    mate_done_payloads = [p for n, p in events if n == "mate_done"]
    sample = mate_done_payloads[0]
    assert "mate" in sample and "round" in sample
    assert "view" in sample and "confidence" in sample
    assert "result" in sample   # 完整 JSON 给前端可点击展开


def test_no_on_event_does_not_break():
    """老调用方不传 on_event 时应该照常工作"""
    cfg = {
        "modes": {"lean": {"enabled_mates": ["m1"], "rounds": 2}},
        "mates": {"m1": {"enabled": True, "model": "deepseek-chat"}},
        "default_model": "deepseek-chat",
    }
    m1 = _mock_mate("m1")
    rt = MagicMock()
    rt.run = MagicMock(return_value={"mate":"red_team","view":"观望","confidence":0,"evidence":[],"extra":{}})
    rt.run_rebuttal = MagicMock()
    dl = MagicMock(); dl.synthesize.return_value = {"direction": "多"}
    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    orch = Orchestrator(cfg=cfg, llm_client=llm, mates={"m1": m1},
                        red_team=rt, decision_lead=dl, audit_logger=audit)
    card = orch.run(symbol="X", mode="lean", data_pack={"symbol": "X", "tags": []})
    assert card["direction"] == "多"
