"""所有分析师 mate 的基类。

子类只需重写 select_fields 决定切片策略,
其他模板渲染 / LLM 调用 / 错误降级 / 审计落盘都在这里统一处理。
"""
import json
import re
import time
from pathlib import Path

class BaseMate:
    """Mate 的通用执行框架。

    生命周期:
      __init__() → render_prompt() → llm.chat() → _parse_json() → 写 audit → 返回 dict

    子类通常只重写 select_fields(),决定从 DataPack 切哪些字段进 prompt。
    特殊角色(experience / red_team / decision_lead)还会重写 run() 加自己的逻辑。
    """

    def __init__(self, name, llm_client, mate_cfg, prompts_dir):
        self.name = name
        self.llm = llm_client
        self.cfg = mate_cfg                # 含 model/temperature/max_tokens/prompt_file
        self.prompts_dir = Path(prompts_dir)
        self._template = None              # lazy 加载,首次 run 时读
        self._shared = None                # 同上,共享片段

    def _load(self):
        """懒加载 prompt 模板 + 三个共享片段(persona/data_format/output_schema)。

        所有 mate 共用 _shared/ 下的三个文件,各自的 prompt 模板用 {{ var }} 占位。
        """
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

    def select_fields(self, data_pack: dict) -> dict:
        """子类重写,返回 DataPack 的瘦身视图。

        默认返回完整 pack(向后兼容)。多数 mate 都会重写,只取自己关心的字段,
        prompt 体积从 ~120K 降到 5-20K token。
        """
        return data_pack

    def render_prompt(self, data_pack: dict, extra_ctx: dict = None) -> str:
        """模板渲染:替换共享片段 + DataPack JSON + extra_ctx。

        sort_keys=True 保证 JSON 输出顺序稳定 → prompt cache 命中率高。
        """
        self._load()
        rendered = self._template
        # 替换三个共享片段
        for k, v in self._shared.items():
            rendered = rendered.replace("{{ " + k + " }}", v)
        # 切片 DataPack 后转 JSON 注入
        sliced = self.select_fields(data_pack)
        rendered = rendered.replace("{{ data_pack_json }}", json.dumps(sliced, ensure_ascii=False, default=str, sort_keys=True))
        # 注入额外上下文(如 round_1_reports_json,position_mgr / decision_lead 用)
        if extra_ctx:
            for k, v in extra_ctx.items():
                rendered = rendered.replace("{{ " + k + " }}", json.dumps(v, ensure_ascii=False, default=str, sort_keys=True) if not isinstance(v, str) else v)
        return rendered

    def _parse_json(self, text: str) -> dict:
        """从 LLM 输出抽取 JSON。容忍 LLM 在 JSON 前后加散文。"""
        text = text.strip()
        # 贪婪匹配第一个 { 到最后一个 } 之间的内容
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)

    def run(self, data_pack: dict, extra_ctx: dict = None, audit_logger=None, audit_id=None, round_num=1) -> dict:
        """执行一次 mate 调用 → 返回结果 dict。

        全部异常都会被捕获并降级为 fallback dict(view="观望", confidence=0, _error=...)。
        这样单个 mate 失败不会传染,Orchestrator 仍能拿到完整的 12 份输出继续后续轮次。
        """
        prompt = ""
        try:
            prompt = self.render_prompt(data_pack, extra_ctx)
        except Exception as e:
            # 模板渲染失败:prompt 文件缺失 / 切片报错 等
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
                # JSON 解析失败:LLM 输出格式不对(很少见)
                parsed = {"view": "观望", "confidence": 0, "evidence": [],
                          "_error": f"JSON parse failed: {e}", "_raw": resp.text[:500]}
            parsed["mate"] = self.name
            # 写审计(如果有 logger)
            if audit_logger and audit_id:
                audit_logger.log_call(
                    audit_id=audit_id, round_num=round_num, mate=self.name,
                    model=self.cfg["model"], prompt=prompt, response=resp.text,
                    tokens=resp.usage, duration_ms=duration_ms,
                )
            return parsed
        except Exception as e:
            # LLM 调用失败:网络 / 超时 / API key 等
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
