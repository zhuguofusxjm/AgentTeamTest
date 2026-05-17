import json
import re
import time
from pathlib import Path

class BaseMate:
    def __init__(self, name, llm_client, mate_cfg, prompts_dir):
        self.name = name
        self.llm = llm_client
        self.cfg = mate_cfg
        self.prompts_dir = Path(prompts_dir)
        self._template = None
        self._shared = None

    def _load(self):
        if self._template is None:
            prompt_file = self.cfg["prompt_file"]
            full_path = self.prompts_dir.parent / prompt_file if not str(prompt_file).startswith(str(self.prompts_dir)) else Path(prompt_file)
            if not full_path.exists():
                full_path = self.prompts_dir / Path(prompt_file).name
            self._template = full_path.read_text(encoding="utf-8")
            shared_dir = self.prompts_dir / "_shared"
            self._shared = {
                "role_persona": (shared_dir / "role_persona.md").read_text(encoding="utf-8"),
                "data_pack_format": (shared_dir / "data_pack_format.md").read_text(encoding="utf-8"),
                "output_schema": (shared_dir / "output_schema.md").read_text(encoding="utf-8"),
            }

    def render_prompt(self, data_pack: dict, extra_ctx: dict = None) -> str:
        self._load()
        rendered = self._template
        for k, v in self._shared.items():
            rendered = rendered.replace("{{ " + k + " }}", v)
        rendered = rendered.replace("{{ data_pack_json }}", json.dumps(data_pack, ensure_ascii=False, default=str))
        if extra_ctx:
            for k, v in extra_ctx.items():
                rendered = rendered.replace("{{ " + k + " }}", json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v)
        return rendered

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)

    def run(self, data_pack: dict, extra_ctx: dict = None, audit_logger=None, audit_id=None, round_num=1) -> dict:
        prompt = ""
        try:
            prompt = self.render_prompt(data_pack, extra_ctx)
        except Exception as e:
            return {"mate": self.name, "view": "观望", "confidence": 0,
                    "evidence": [], "_error": f"render failed: {e}"}
        messages = [{"role": "user", "content": prompt}]
        start = time.time()
        try:
            resp = self.llm.chat(
                model=self.cfg["model"],
                messages=messages,
                temperature=self.cfg.get("temperature"),
                max_tokens=self.cfg.get("max_tokens"),
                response_format="json",
            )
            duration_ms = int((time.time() - start) * 1000)
            try:
                parsed = self._parse_json(resp.text)
            except Exception as e:
                parsed = {"view": "观望", "confidence": 0, "evidence": [],
                          "_error": f"JSON parse failed: {e}", "_raw": resp.text[:500]}
            parsed["mate"] = self.name
            if audit_logger and audit_id:
                audit_logger.log_call(
                    audit_id=audit_id, round_num=round_num, mate=self.name,
                    model=self.cfg["model"], prompt=prompt, response=resp.text,
                    tokens=resp.usage, duration_ms=duration_ms,
                )
            return parsed
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            err_result = {"mate": self.name, "view": "观望", "confidence": 0,
                          "evidence": [], "_error": f"LLM call failed: {e}"}
            if audit_logger and audit_id:
                audit_logger.log_call(
                    audit_id=audit_id, round_num=round_num, mate=self.name,
                    model=self.cfg.get("model", "?"), prompt=prompt, response=str(e),
                    tokens={}, duration_ms=duration_ms,
                )
            return err_result
