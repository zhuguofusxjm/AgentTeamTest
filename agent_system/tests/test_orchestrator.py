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
