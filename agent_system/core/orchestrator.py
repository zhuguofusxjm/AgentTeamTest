import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime

ROUND_2_RESPONSE_PROMPT = """你是 {mate_name} 分析师。第 1 轮你的判断是:
{your_round_1_json}

蒋军(Red Team)对多数派(view={majority_view})的反驳如下:
{rebuttal_json}

请基于反驳和原始数据,决定是否坚持原观点。如果反驳有据,适当下调 confidence 或修正 view。
严格输出 JSON:
{{
  "mate": "{mate_name}",
  "keeps_view": <true|false>,
  "updated_view": "<多|空|观望>",
  "updated_confidence": <0-100>,
  "note": "<一句话解释>"
}}

只输出 JSON,不要 Markdown,不要其他文字。"""

class Orchestrator:
    def __init__(self, cfg, llm_client, mates, red_team=None, decision_lead=None,
                 audit_logger=None):
        self.cfg = cfg
        self.llm = llm_client
        self.mates = mates
        self.red_team = red_team
        self.decision_lead = decision_lead
        self.audit = audit_logger

    def _enabled_mates_for_mode(self, mode: str) -> list:
        mode_cfg = self.cfg["modes"][mode]
        mode_list = mode_cfg["enabled_mates"]
        mates_cfg = self.cfg["mates"]
        return [m for m in mode_list if mates_cfg.get(m, {}).get("enabled", False)]

    def _run_round_1_batch_1(self, mate_names: list, data_pack: dict, audit_id: str) -> list:
        results = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {
                ex.submit(self.mates[n].run, data_pack, None, self.audit, audit_id, 1): n
                for n in mate_names
            }
            for f in as_completed(futures):
                results.append(f.result())

        if self.red_team is not None and "red_team" not in mate_names:
            rt_result = self.red_team.run(data_pack, None, self.audit, audit_id, 1)
            results.append(rt_result)
        return results

    def _run_round_1_batch_2(self, data_pack: dict, batch_1_results: list,
                              audit_id: str) -> dict:
        if "position_mgr" not in self.mates:
            return None
        return self.mates["position_mgr"].run(
            data_pack, extra_ctx={"round_1_reports_json": batch_1_results},
            audit_logger=self.audit, audit_id=audit_id, round_num=1,
        )

    def _majority_view(self, reports: list) -> str:
        views = [r.get("view") for r in reports if r.get("view") in ("多", "空")]
        if not views:
            return "观望"
        return Counter(views).most_common(1)[0][0]

    def _respond_to_rebuttal(self, mate_name: str, your_round_1: dict, rebuttal: dict,
                              majority_view: str, audit_id: str) -> dict:
        prompt = ROUND_2_RESPONSE_PROMPT.format(
            mate_name=mate_name,
            your_round_1_json=json.dumps(your_round_1, ensure_ascii=False),
            majority_view=majority_view,
            rebuttal_json=json.dumps(rebuttal, ensure_ascii=False),
        )
        model = self.cfg["mates"].get(mate_name, {}).get("model") or self.cfg.get("default_model", "deepseek-chat")
        start = time.time()
        try:
            resp = self.llm.chat(model=model, messages=[{"role": "user", "content": prompt}],
                                  temperature=0.3, max_tokens=500, response_format="json")
            duration_ms = int((time.time() - start) * 1000)
            try:
                m = re.search(r'\{.*\}', resp.text, re.DOTALL)
                parsed = json.loads(m.group(0) if m else resp.text)
            except Exception:
                parsed = {"mate": mate_name, "keeps_view": True, "note": "(parse failed)",
                          "_raw": resp.text[:500]}
            if self.audit and audit_id:
                self.audit.log_call(audit_id=audit_id, round_num=2,
                                     mate=f"{mate_name}_response",
                                     model=model, prompt=prompt, response=resp.text,
                                     tokens=resp.usage, duration_ms=duration_ms)
            return parsed
        except Exception as e:
            return {"mate": mate_name, "keeps_view": True, "note": f"(call failed: {e})"}

    def _run_round_2(self, data_pack: dict, round_1_reports: list,
                     audit_id: str) -> dict:
        if self.red_team is None:
            return {"rebuttal": None, "responses": [], "majority": "观望"}
        majority = self._majority_view(round_1_reports)
        rebuttal = self.red_team.run_rebuttal(
            data_pack=data_pack, round_1_reports=round_1_reports,
            majority_view=majority, audit_logger=self.audit, audit_id=audit_id,
        )
        majority_reports = [r for r in round_1_reports if r.get("view") == majority]
        majority_reports.sort(key=lambda r: r.get("confidence", 0), reverse=True)
        top3 = majority_reports[:3]
        responses = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = []
            for r in top3:
                mate_name = r.get("mate")
                if not mate_name:
                    continue
                futures.append(ex.submit(
                    self._respond_to_rebuttal, mate_name, r, rebuttal, majority, audit_id
                ))
            for f in as_completed(futures):
                responses.append(f.result())
        return {"rebuttal": rebuttal, "responses": responses, "majority": majority}

    def _run_round_3(self, data_pack: dict, round_1_reports: list,
                     round_2_debate: dict, audit_id: str) -> dict:
        if self.decision_lead is None:
            return {"direction": "观望", "_error": "decision_lead 未注册"}
        return self.decision_lead.synthesize(
            data_pack=data_pack, round_1_reports=round_1_reports,
            round_2_debate=round_2_debate, audit_logger=self.audit, audit_id=audit_id,
        )

    def run(self, symbol: str, mode: str, data_pack: dict, session_key: str = None) -> dict:
        if session_key is None:
            session_key = f"{symbol}_{int(datetime.now().timestamp())}"
        audit_id = self.audit.start_session(prefix="decision", session_key=session_key) if self.audit else None
        rounds = self.cfg["modes"][mode].get("rounds", 3)

        enabled = self._enabled_mates_for_mode(mode)
        batch_1_mates = [m for m in enabled if m != "position_mgr"]
        batch_1_results = self._run_round_1_batch_1(batch_1_mates, data_pack, audit_id)

        if "position_mgr" in enabled:
            position_mgr_result = self._run_round_1_batch_2(data_pack, batch_1_results, audit_id)
            if position_mgr_result:
                batch_1_results.append(position_mgr_result)

        round_2_debate = {"rebuttal": None, "responses": [], "majority": "观望"}
        if rounds >= 3:
            round_2_debate = self._run_round_2(data_pack, batch_1_results, audit_id)

        card = self._run_round_3(data_pack, batch_1_results, round_2_debate, audit_id)

        if self.audit and audit_id:
            self.audit.finalize(audit_id, final_card=card)
        return card
