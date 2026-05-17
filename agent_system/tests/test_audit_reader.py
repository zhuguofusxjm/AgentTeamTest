from agent_system.core.audit_reader import read_round_1_mate_views


def test_extracts_mate_views(tmp_path):
    audit_path = tmp_path / "decision_X_1.json"
    audit_path.write_text("""
{
  "session_key": "X_1",
  "rounds": [
    {"round": 1, "calls": [
      {"mate": "trend_multi_tf", "model": "deepseek-chat",
       "response": "{\\"view\\": \\"多\\", \\"confidence\\": 80, \\"evidence\\": [\\"e1\\", \\"e2\\"]}"},
      {"mate": "red_team", "model": "deepseek-chat",
       "response": "{\\"view\\": \\"空\\", \\"confidence\\": 60, \\"evidence\\": [\\"r1\\"]}"}
    ]},
    {"round": 3, "calls": [
      {"mate": "decision_lead", "model": "deepseek-chat", "response": "{}"}
    ]}
  ],
  "final_card": {}
}
""", encoding="utf-8")

    views = read_round_1_mate_views(str(audit_path))
    assert len(views) == 2
    by_name = {v["mate"]: v for v in views}
    assert by_name["trend_multi_tf"]["view"] == "多"
    assert by_name["trend_multi_tf"]["confidence"] == 80
    assert by_name["red_team"]["view"] == "空"


def test_handles_missing_file():
    assert read_round_1_mate_views("does_not_exist.json") == []


def test_skips_unparseable_response(tmp_path):
    audit_path = tmp_path / "a.json"
    audit_path.write_text("""
{
  "rounds": [
    {"round": 1, "calls": [
      {"mate": "broken", "response": "not json at all"},
      {"mate": "ok", "response": "{\\"view\\": \\"多\\", \\"confidence\\": 50}"}
    ]}
  ]
}
""", encoding="utf-8")
    views = read_round_1_mate_views(str(audit_path))
    assert len(views) == 1
    assert views[0]["mate"] == "ok"
