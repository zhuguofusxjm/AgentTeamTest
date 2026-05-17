import json
from unittest.mock import MagicMock
from agent_system.core.orchestrator import Orchestrator
from agent_system.providers.base import LLMResponse
from agent_system.mates.base import BaseMate

def _build_mock_mate(name):
    class _M(BaseMate):
        def run(self, data_pack, extra_ctx=None, audit_logger=None, audit_id=None, round_num=1):
            return {"mate": name, "view": "多", "confidence": 70, "evidence": ["mock"], "extra": {}}
    return _M(name=name, llm_client=None, mate_cfg={"model": "deepseek-chat", "prompt_file": ""}, prompts_dir="")

def test_full_mode_end_to_end_with_mocks():
    cfg = {
        "modes": {"full": {"enabled_mates": ["trend_multi_tf", "funding_rate",
                                              "smart_money", "position_mgr"], "rounds": 3}},
        "mates": {
            "trend_multi_tf": {"enabled": True, "model": "deepseek-chat"},
            "funding_rate": {"enabled": True, "model": "deepseek-chat"},
            "smart_money": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
            "red_team": {"enabled": True, "model": "deepseek-chat"},
            "decision_lead": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    mates = {n: _build_mock_mate(n) for n in ["trend_multi_tf", "funding_rate", "smart_money", "position_mgr"]}

    rt = MagicMock()
    rt.run = MagicMock(return_value={"mate": "red_team", "view": "空", "confidence": 50, "evidence": [], "extra": {}})
    rt.run_rebuttal = MagicMock(return_value={"mate": "red_team", "view": "空", "extra": {"rebuttal": "..."}})

    dl = MagicMock()
    dl.synthesize.return_value = {
        "direction": "多", "entry_price": 3120, "stop_loss": 3050, "take_profit": 3260,
        "confidence": 65, "key_evidence": ["e1"], "key_risks": ["r1"],
    }

    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    llm.chat.return_value = LLMResponse(text='{"keeps_view":true}', usage={}, model="x", raw={})
    orch = Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=rt, decision_lead=dl, audit_logger=audit)
    card = orch.run(symbol="ETHUSDT", mode="full",
                    data_pack={"symbol": "ETHUSDT", "tags": []})
    assert card["direction"] == "多"
    assert card["confidence"] == 65
    assert audit.start_session.called
    assert audit.finalize.called
