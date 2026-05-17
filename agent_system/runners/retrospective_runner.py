import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from agent_system.data.db import get_conn
from agent_system.data.experience_store import find_by_tag_signature, create_experience, update_experience
from agent_system.core.decision_metrics import compute_execution_metrics
from agent_system.core.audit_reader import read_round_1_mate_views

MIN_SAMPLES_FOR_NEW_GROUP = 3

RETRO_PROMPT = """你是策略复盘官。基于一组同场景标签下的已完结决策,做归因分析并提炼可复用的经验。

## 你拿到的信息(每个决策包含)
- card: 当时的决策卡片(direction/entry/SL/TP/key_evidence/key_risks/confidence)
- status: win / loss / expired
- realized_pnl_pct: 实际收益率
- metrics: 过程数据
  - mfe_pct: 最大有利偏离 (能盈利多少的极限)
  - mae_pct: 最大不利偏离 (中途最深亏损)
  - time_to_close_hours: 持有时长
  - path_shape: direct(直奔) / v_reversal(V反) / false_breakout(假突破) / choppy(震荡) / unknown
- mate_views: 11 个 Mate 第一轮独立判断时各自的 view+confidence

## 归因要点 (必须做)
1. **方向归因**: 在赢的决策中,哪些 Mate 的 view 与最终方向一致?在输的决策中,哪个 Mate 给出了误导性的高 confidence?
2. **过程归因**:
   - 多次 mae_pct 接近 sl 距离 → 止损过紧或入场点不佳
   - mfe_pct >> realized_pnl_pct → 止盈设得太近,或没用移动止盈
   - false_breakout 多 → 在该场景下追突破容易被反插
   - v_reversal 多 → 该场景适合等回踩再进
3. **场景固有性**: 这种 tag 组合下,系统性偏向哪一方?是否某些 Mate 在这场景里持续不可信?

## 输出 (严格 JSON,不要 Markdown)
{
  "scenario_summary": "<一句话场景描述>",
  "lesson": "<150-300 字的复盘文本,必须包含: 1) 这种场景下哪些信号最可信; 2) 哪些 Mate 容易误导,具体在何种条件下; 3) 入场/止损/止盈应如何调整>",
  "applicable_when": "<触发条件,简洁>",
  "caveats": "<已知失效条件>",
  "mate_attribution": {
    "<mate_name>": "trustworthy" | "neutral" | "misleading"
  }
}

## 场景标签
{{ tags }}

## 决策数据
{{ decisions_json }}
"""


class RetrospectiveRunner:
    def __init__(self, cfg, llm_client, db_path, binance=None, audit_logger=None):
        self.cfg = cfg
        self.llm = llm_client
        self.db_path = db_path
        self.binance = binance
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

    def _enrich(self, decision: dict) -> dict:
        """Attach execution metrics and per-Mate round-1 views to the decision."""
        card = json.loads(decision.get("card_json") or "{}")
        slim_card = {
            k: card.get(k) for k in
            ("direction", "entry_price", "stop_loss", "take_profit",
             "confidence", "key_evidence", "key_risks", "execution_plan")
        }
        out = {
            "decision_id": decision.get("decision_id"),
            "symbol": decision.get("symbol"),
            "trigger_mode": decision.get("trigger_mode"),
            "created_at": decision.get("created_at"),
            "closed_at": decision.get("closed_at"),
            "status": decision.get("status"),
            "realized_pnl_pct": decision.get("realized_pnl_pct"),
            "card": slim_card,
        }
        if self.binance is not None:
            try:
                out["metrics"] = compute_execution_metrics(decision, self.binance)
            except Exception as e:
                out["metrics"] = {"_error": str(e)}
        audit_path = decision.get("audit_path") or ""
        if audit_path:
            out["mate_views"] = read_round_1_mate_views(audit_path)
        return out

    def _llm_retro(self, tags: list, enriched_decisions: list) -> dict:
        prompt = RETRO_PROMPT.replace("{{ tags }}", json.dumps(tags, ensure_ascii=False))
        prompt = prompt.replace("{{ decisions_json }}",
                                 json.dumps(enriched_decisions, ensure_ascii=False, default=str))
        model = self.cfg.get("default_model", "deepseek-chat")
        resp = self.llm.chat(model=model, messages=[{"role": "user", "content": prompt}],
                             temperature=0.3, max_tokens=2000, response_format="json")
        try:
            m = re.search(r'\{.*\}', resp.text, re.DOTALL)
            return json.loads(m.group(0) if m else resp.text)
        except Exception:
            return {"scenario_summary": "(parse failed)", "lesson": resp.text[:500],
                    "applicable_when": "", "caveats": "", "mate_attribution": {}}

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
            outcome = self._outcome_stats(decisions)
            decision_ids = [d["decision_id"] for d in decisions]

            if existing is None and len(decisions) < MIN_SAMPLES_FOR_NEW_GROUP:
                print(f"[retro] skip new group {tags}: only {len(decisions)} samples")
                continue

            enriched = [self._enrich(d) for d in decisions]
            retro = self._llm_retro(tags, enriched)

            if existing:
                old_outcome = json.loads(existing["outcome_stats"] or "{}")
                merged = {k: old_outcome.get(k, 0) + outcome.get(k, 0)
                          for k in ("win", "loss", "expired")}
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
