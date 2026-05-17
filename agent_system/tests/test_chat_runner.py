import json
from unittest.mock import MagicMock
from agent_system.data.db import init_new_tables
from agent_system.data.chat_store import save_message, list_messages
from agent_system.data.decisions_store import save_decision
from agent_system.runners.chat_runner import ChatRunner
from agent_system.providers.base import LLMResponse


def _mock_llm(intent_response, follow_up_text=None):
    """Returns a MagicMock LLM. First chat() returns intent JSON,
    optionally a second chat() returns follow-up natural-language text."""
    llm = MagicMock()
    responses = [LLMResponse(text=json.dumps(intent_response, ensure_ascii=False),
                              usage={"total_tokens": 1}, model="deepseek-chat", raw={})]
    if follow_up_text is not None:
        responses.append(LLMResponse(text=follow_up_text, usage={"total_tokens": 1},
                                      model="deepseek-chat", raw={}))
    llm.chat.side_effect = responses
    return llm


def _seed_decision_in_session(db, session_id, symbol="ETHUSDT"):
    """Place a fake completed decision message in the session."""
    card = {
        "direction": "空", "entry_price": 100, "stop_loss": 105, "take_profit": 90,
        "confidence": 70, "key_evidence": ["EMA200 下方"], "key_risks": ["假反弹"],
        "execution_plan": "分批进场",
    }
    decision_id = save_decision(db, symbol, "chat", card,
                                 ["funding=normal"], "")
    save_message(db, session_id, "user", "帮我分析 ETHUSDT")
    save_message(db, session_id, "assistant", json.dumps(card, ensure_ascii=False),
                 decision_id=decision_id)
    return decision_id


def _build_runner(db, llm):
    return ChatRunner(
        cfg={"default_model": "deepseek-chat"},
        llm_client=llm, orchestrator=MagicMock(), binance=MagicMock(),
        db_path=db, data_packer=MagicMock(),
    )


def test_follow_up_uses_last_decision_in_session(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    session_id = "s1"
    decision_id = _seed_decision_in_session(db, session_id)

    llm = _mock_llm(
        intent_response={"intent": "follow_up", "symbol": None, "extra": {}},
        follow_up_text="本次共有 11 个分析师参与,看空 7 个,观望 4 个...",
    )
    runner = _build_runner(db, llm)
    result = runner.handle_message(session_id, "几个分析师参与?各自结论?")

    assert result["type"] == "follow_up_answer"
    assert result["decision_id"] == decision_id
    assert "11 个分析师" in result["message"]


def test_follow_up_without_prior_decision_prompts_for_symbol(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    llm = _mock_llm(
        intent_response={"intent": "follow_up", "symbol": None, "extra": {}},
    )
    runner = _build_runner(db, llm)
    result = runner.handle_message("s_empty", "你们怎么看?")

    assert result["type"] == "follow_up_answer"
    assert result["decision_id"] is None
    assert "还没产生过决策" in result["message"]


def test_intent_prompt_includes_recent_history(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    save_message(db, "s2", "user", "之前的对话")
    save_message(db, "s2", "assistant", "之前的回复")

    llm = _mock_llm(
        intent_response={"intent": "chitchat", "symbol": None, "extra": {}},
    )
    runner = _build_runner(db, llm)
    runner.handle_message("s2", "嗨")

    sent = llm.chat.call_args.kwargs["messages"][0]["content"]
    assert "之前的对话" in sent
    assert "之前的回复" in sent


def test_follow_up_translates_mate_ids_to_display_names(tmp_path):
    """follow_up 发给 LLM 的 prompt 必须用中文角色名,不带英文 mate id"""
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    sid = "s_translate"
    # 写一份 audit JSON 含 trend_multi_tf / red_team 两个 round-1 输出
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({
        "rounds": [{
            "round": 1, "calls": [
                {"mate": "trend_multi_tf",
                 "response": json.dumps({"view":"空","confidence":75,"evidence":["e1"]})},
                {"mate": "red_team",
                 "response": json.dumps({"view":"空","confidence":70,"evidence":["r1"]})},
            ]
        }]
    }, ensure_ascii=False), encoding="utf-8")

    from agent_system.data.decisions_store import save_decision
    did = save_decision(db, "ETHUSDT", "chat",
                        {"direction":"空","entry_price":100,"stop_loss":105,"take_profit":90,
                         "confidence":70,"key_evidence":[],"key_risks":[]},
                        ["funding=normal"], str(audit))
    save_message(db, sid, "user", "之前问过 ETHUSDT")
    save_message(db, sid, "assistant", "{}", decision_id=did)

    llm = _mock_llm(
        intent_response={"intent": "follow_up", "symbol": None, "extra": {}},
        follow_up_text="蒋军认为有风险...",
    )
    runner = _build_runner(db, llm)
    runner.handle_message(sid, "为什么这样判断?")

    follow_up_prompt = llm.chat.call_args_list[1].kwargs["messages"][0]["content"]
    # mate id 不应出现在 follow_up prompt 里
    assert "trend_multi_tf" not in follow_up_prompt
    assert "red_team" not in follow_up_prompt
    # 中文角色名应出现
    assert "周期师" in follow_up_prompt
    assert "蒋军" in follow_up_prompt


def test_single_analysis_still_works(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    llm = _mock_llm(
        intent_response={"intent": "single_analysis", "symbol": "BTCUSDT", "extra": {}},
    )
    runner = _build_runner(db, llm)
    runner.build_pack = MagicMock(return_value={"symbol": "BTCUSDT", "tags": []})
    runner.orch.run = MagicMock(return_value={
        "direction": "多", "confidence": 60, "key_evidence": [], "key_risks": []
    })
    result = runner.handle_message("s3", "帮我分析 BTC")
    assert result["type"] == "decision_card"
    assert result["card"]["direction"] == "多"
