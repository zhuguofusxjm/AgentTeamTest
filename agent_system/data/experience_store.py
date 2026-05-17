import json
from datetime import datetime, timedelta
from agent_system.data.db import get_conn

def create_experience(db_path, tags, scenario_summary, decisions_referenced,
                       outcome_stats, lesson, applicable_when, caveats) -> int:
    conn = get_conn(db_path)
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            """INSERT INTO experiences (tags, scenario_summary, decisions_referenced,
               outcome_stats, lesson, applicable_when, caveats, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (json.dumps(sorted(tags), ensure_ascii=False), scenario_summary,
             json.dumps(decisions_referenced), json.dumps(outcome_stats),
             lesson, applicable_when, caveats, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def update_experience(db_path, eid, new_decision_ids=None, new_outcome_stats=None,
                       new_lesson=None, new_applicable_when=None, new_caveats=None):
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM experiences WHERE experience_id = ?", (eid,)).fetchone()
        if not row:
            return
        existing_ids = json.loads(row["decisions_referenced"] or "[]")
        if new_decision_ids:
            for did in new_decision_ids:
                if did not in existing_ids:
                    existing_ids.append(did)
        outcome = json.loads(row["outcome_stats"] or "{}")
        if new_outcome_stats:
            outcome = new_outcome_stats
        lesson = new_lesson if new_lesson is not None else row["lesson"]
        aw = new_applicable_when if new_applicable_when is not None else row["applicable_when"]
        cv = new_caveats if new_caveats is not None else row["caveats"]
        conn.execute(
            """UPDATE experiences SET decisions_referenced=?, outcome_stats=?,
               lesson=?, applicable_when=?, caveats=?, updated_at=?
               WHERE experience_id = ?""",
            (json.dumps(existing_ids), json.dumps(outcome), lesson, aw, cv,
             datetime.now().isoformat(), eid),
        )
        conn.commit()
    finally:
        conn.close()

def find_by_tag_signature(db_path, tags) -> dict:
    """精确匹配: 排序后的 tags 完全相等"""
    sig = json.dumps(sorted(tags), ensure_ascii=False)
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM experiences WHERE tags = ?", (sig,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def search_by_tags(db_path, query_tags, limit=5, days=90) -> list:
    """模糊匹配: 任一标签命中, 按命中数量倒序"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM experiences WHERE updated_at > ?", (cutoff,)
        ).fetchall()
        scored = []
        qset = set(query_tags)
        for r in rows:
            tags = set(json.loads(r["tags"] or "[]"))
            hit = len(tags & qset)
            if hit > 0:
                outcome = json.loads(r["outcome_stats"] or "{}")
                clarity = abs(outcome.get("win", 0) - outcome.get("loss", 0))
                scored.append((hit, clarity, dict(r)))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [s[2] for s in scored[:limit]]
    finally:
        conn.close()
