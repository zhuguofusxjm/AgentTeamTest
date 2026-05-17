"""Tests for the retrospective runner — focuses on the new behaviors:
- enriches decisions with metrics + mate_views before sending to LLM
- skips brand new tag groups with < 3 samples
- existing groups update even with 1 new sample
"""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from agent_system.data.db import init_new_tables, get_conn
from agent_system.data.decisions_store import save_decision, update_decision_status
from agent_system.data.experience_store import create_experience, find_by_tag_signature
from agent_system.runners.retrospective_runner import RetrospectiveRunner
from agent_system.providers.base import LLMResponse


def _make_card(direction="多", entry=100, sl=95, tp=110, conf=70):
    return {
        "direction": direction, "entry_price": entry, "stop_loss": sl, "take_profit": tp,
        "confidence": conf, "key_evidence": ["e1"], "key_risks": ["r1"],
    }


def _close_just_now(db_path, decision_id, status="win", pnl=10.0):
    update_decision_status(db_path, decision_id, status=status, realized_pnl_pct=pnl)


def _make_audit_file(tmp_path, name, mate_views: list):
    """Build a minimal audit JSON."""
    calls = [{"mate": v["mate"],
              "model": "deepseek-chat",
              "response": json.dumps({
                  "view": v["view"],
                  "confidence": v["confidence"],
                  "evidence": v.get("evidence", [])
              }, ensure_ascii=False)} for v in mate_views]
    audit_path = tmp_path / name
    audit_path.write_text(json.dumps({
        "session_key": "x",
        "rounds": [{"round": 1, "calls": calls}],
        "final_card": {},
    }, ensure_ascii=False), encoding="utf-8")
    return str(audit_path)


def _build_runner(db, llm, binance):
    return RetrospectiveRunner(
        cfg={"default_model": "deepseek-chat"},
        llm_client=llm, db_path=db, binance=binance,
    )


def test_skips_new_group_with_too_few_samples(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    did = save_decision(db, "ETHUSDT", "chat", _make_card(),
                        ["funding=normal", "smart_money=normal", "volatility=compressed"], "")
    _close_just_now(db, did, "win", 8.0)

    llm = MagicMock()
    binance = MagicMock()
    binance.get_klines.return_value = []
    runner = _build_runner(db, llm, binance)
    runner.run_daily()

    # 标签组样本不足 3,且经验库无对应条目 → 不调 LLM,不创建经验
    assert llm.chat.call_count == 0
    e = find_by_tag_signature(db, ["funding=normal", "smart_money=normal", "volatility=compressed"])
    assert e is None


def test_existing_group_updates_with_one_sample(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tags = ["funding=normal", "smart_money=normal", "volatility=compressed"]
    eid = create_experience(db, tags=tags, scenario_summary="老经验",
                             decisions_referenced=[99],
                             outcome_stats={"win": 2, "loss": 1, "expired": 0},
                             lesson="历史复盘", applicable_when="", caveats="")
    did = save_decision(db, "ETHUSDT", "chat", _make_card(), tags, "")
    _close_just_now(db, did, "win", 8.0)

    llm = MagicMock()
    llm.chat.return_value = LLMResponse(
        text=json.dumps({"scenario_summary": "更新", "lesson": "新洞察",
                         "applicable_when": "", "caveats": "", "mate_attribution": {}}),
        usage={"total_tokens": 1}, model="deepseek-chat", raw={})
    binance = MagicMock()
    binance.get_klines.return_value = [
        [0, "100", "112", "99", "111", "1", 0, "1", 0, "1", "1", "0"],
    ]
    runner = _build_runner(db, llm, binance)
    runner.run_daily()

    # 已有经验组,即使只有 1 个新样本也复盘
    assert llm.chat.call_count == 1
    e = find_by_tag_signature(db, tags)
    assert e["experience_id"] == eid
    assert "历史复盘" in e["lesson"]   # 旧 lesson 保留
    assert "新洞察" in e["lesson"]      # 新 lesson 追加
    out = json.loads(e["outcome_stats"])
    assert out == {"win": 3, "loss": 1, "expired": 0}  # 累加


def test_prompt_includes_metrics_and_mate_views(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    audit = _make_audit_file(tmp_path, "audit_1.json", [
        {"mate": "trend_multi_tf", "view": "多", "confidence": 85},
        {"mate": "red_team", "view": "空", "confidence": 50},
    ])
    tags = ["funding=normal"]
    create_experience(db, tags=tags, scenario_summary="",
                       decisions_referenced=[], outcome_stats={"win": 0, "loss": 0, "expired": 0},
                       lesson="", applicable_when="", caveats="")
    did = save_decision(db, "ETHUSDT", "chat", _make_card(), tags, audit)
    _close_just_now(db, did, "win", 9.0)

    llm = MagicMock()
    llm.chat.return_value = LLMResponse(
        text='{"scenario_summary":"x","lesson":"L","applicable_when":"","caveats":"","mate_attribution":{}}',
        usage={"total_tokens": 1}, model="deepseek-chat", raw={})
    binance = MagicMock()
    binance.get_klines.return_value = [
        [0, "100", "111", "99.5", "110.5", "1", 0, "1", 0, "1", "1", "0"],
    ]
    runner = _build_runner(db, llm, binance)
    runner.run_daily()

    sent_prompt = llm.chat.call_args.kwargs["messages"][0]["content"]
    # metrics 已注入
    assert "mfe_pct" in sent_prompt
    assert "path_shape" in sent_prompt
    # mate_views 已注入
    assert "trend_multi_tf" in sent_prompt
    assert "red_team" in sent_prompt
