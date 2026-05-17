import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from agent_system.data.db import get_conn
from agent_system.data.experience_store import find_by_tag_signature, create_experience, update_experience

RETRO_PROMPT = """你是策略复盘官。基于以下已完结的决策列表(同一场景标签组),
1) 总结该场景的成败规律
2) 提炼 1 段 lesson(自然语言, 100-200 字)
3) 给出 applicable_when(触发条件,简洁)
4) 给出 caveats(失效条件)

输出严格 JSON:
{
  "scenario_summary": "<一句话场景描述>",
  "lesson": "<复盘文本>",
  "applicable_when": "<...>",
  "caveats": "<...>"
}

场景标签: {{ tags }}
该场景下的决策记录(已标注 win/loss/expired 与 realized_pnl_pct):
{{ decisions_json }}
"""

class RetrospectiveRunner:
    def __init__(self, cfg, llm_client, db_path, audit_logger=None):
        self.cfg = cfg
        self.llm = llm_client
        self.db_path = db_path
        self.audit = audit_logger

    def _closed_decisions_in_window(self, hours: int = 24) -> list:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        conn = get_conn(self.db_path)
        try:
            rows = conn.execute(
                """SELECT * FROM decisions
                   WHERE status IN ('win','loss','expired')
                     AND closed_at > ?""", (cutoff,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _group_by_tags(self, decisions: list) -> dict:
        groups = defaultdict(list)
        for d in decisions:
            tags = sorted(json.loads(d.get("tags") or "[]"))
            groups[tuple(tags)].append(d)
        return dict(groups)

    def _llm_retro(self, tags: list, decisions: list) -> dict:
        prompt = RETRO_PROMPT.replace("{{ tags }}", json.dumps(tags, ensure_ascii=False))
        prompt = prompt.replace("{{ decisions_json }}", json.dumps(decisions, ensure_ascii=False, default=str))
        model = self.cfg.get("default_model", "deepseek-chat")
        resp = self.llm.chat(model=model, messages=[{"role": "user", "content": prompt}],
                             temperature=0.3, max_tokens=1500, response_format="json")
        try:
            m = re.search(r'\{.*\}', resp.text, re.DOTALL)
            return json.loads(m.group(0) if m else resp.text)
        except Exception:
            return {"scenario_summary": "(parse failed)", "lesson": resp.text[:500],
                    "applicable_when": "", "caveats": ""}

    def _outcome_stats(self, decisions: list) -> dict:
        stats = {"win": 0, "loss": 0, "expired": 0}
        for d in decisions:
            s = d.get("status")
            if s in stats:
                stats[s] += 1
        return stats

    def run_daily(self):
        closed = self._closed_decisions_in_window(hours=24)
        if not closed:
            print("[retro] no closed decisions in last 24h")
            return
        groups = self._group_by_tags(closed)
        for tags_tuple, decisions in groups.items():
            tags = list(tags_tuple)
            if not tags:
                continue
            existing = find_by_tag_signature(self.db_path, tags)
            retro = self._llm_retro(tags, decisions)
            outcome = self._outcome_stats(decisions)
            decision_ids = [d["decision_id"] for d in decisions]
            if existing:
                old_outcome = json.loads(existing["outcome_stats"] or "{}")
                merged = {k: old_outcome.get(k, 0) + outcome.get(k, 0) for k in ("win","loss","expired")}
                update_experience(
                    self.db_path, existing["experience_id"],
                    new_decision_ids=decision_ids,
                    new_outcome_stats=merged,
                    new_lesson=retro.get("lesson"),
                    new_applicable_when=retro.get("applicable_when"),
                    new_caveats=retro.get("caveats"),
                )
            else:
                create_experience(
                    self.db_path, tags=tags,
                    scenario_summary=retro.get("scenario_summary", ""),
                    decisions_referenced=decision_ids,
                    outcome_stats=outcome,
                    lesson=retro.get("lesson", ""),
                    applicable_when=retro.get("applicable_when", ""),
                    caveats=retro.get("caveats", ""),
                )
        print(f"[retro] processed {len(groups)} tag groups, {len(closed)} decisions")
