import json
from agent_system.data.db import init_new_tables
from agent_system.data.experience_store import (
    create_experience, update_experience, find_by_tag_signature, search_by_tags,
)

def test_create_and_find(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    eid = create_experience(db,
        tags=["funding=extreme_high", "smart_money=divergence"],
        scenario_summary="高费率分歧",
        decisions_referenced=[1, 2],
        outcome_stats={"win": 1, "loss": 1, "expired": 0},
        lesson="..", applicable_when="..", caveats="..")
    e = find_by_tag_signature(db, ["funding=extreme_high", "smart_money=divergence"])
    assert e["experience_id"] == eid

def test_update(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    eid = create_experience(db, tags=["a"], scenario_summary="s",
                             decisions_referenced=[1], outcome_stats={"win": 1, "loss": 0, "expired": 0},
                             lesson="L1", applicable_when="", caveats="")
    update_experience(db, eid,
                       new_decision_ids=[2, 3],
                       new_outcome_stats={"win": 2, "loss": 1, "expired": 0},
                       new_lesson="L2")
    e = find_by_tag_signature(db, ["a"])
    assert json.loads(e["decisions_referenced"]) == [1, 2, 3]
    assert e["lesson"] == "L2"

def test_search_by_tags(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    create_experience(db, tags=["a", "b"], scenario_summary="",
                       decisions_referenced=[], outcome_stats={"win":0,"loss":0,"expired":0},
                       lesson="L1", applicable_when="", caveats="")
    create_experience(db, tags=["b", "c"], scenario_summary="",
                       decisions_referenced=[], outcome_stats={"win":0,"loss":0,"expired":0},
                       lesson="L2", applicable_when="", caveats="")
    matches = search_by_tags(db, query_tags=["b"], limit=5, days=90)
    assert len(matches) == 2
