"""审计日志记录器 — 把每次圆桌的 prompt/response/tokens 完整落盘。

每次决策对应一个 audit_id,流程:
  start_session(prefix, session_key)  → 返回 audit_id
  log_call(audit_id, round_num, mate, prompt, response, ...)  ← 每次 LLM 调用都记
  finalize(audit_id, final_card)  → 写 JSON 到 tracks/<prefix>_<session_key>.json

落盘的 JSON 用于:
- web 端追问时回放各 mate 的 view+confidence
- 复盘官 (experience mate) 提取历史决策的归因
- 调试 prompt 质量
"""
import json
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

# 文件名安全字符:字母/数字/点/下划线/横线
_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")

def _sanitize(s: str) -> str:
    """把字符串清理成安全文件名,防止路径穿越。"""
    if not isinstance(s, str):
        return "unknown"
    cleaned = _SAFE_RE.sub("_", s)
    # 折叠 ".." 序列,避免 path-traversal (foo/../etc 之类)
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    return cleaned or "unknown"

class AuditLogger:
    """线程安全的审计记录器。

    所有 session 在内存中(self._sessions),finalize 时一次性写盘。
    用一把 lock 保证并发 mate 调用 log_call 时不会撞车。
    """

    def __init__(self, audit_dir: str):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._sessions = {}     # audit_id -> session dict
        self._lock = threading.Lock()

    def start_session(self, prefix: str, session_key: str) -> str:
        """开启一个新会话,返回 uuid 作为 audit_id。

        prefix 决定文件名前缀(如 "decision"),
        session_key 用于文件名后缀(通常是 symbol_timestamp)。
        """
        audit_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[audit_id] = {
                "prefix": prefix,
                "session_key": session_key,
                "started_at": datetime.now().isoformat(),
                "rounds": {},      # round_num -> list of call records
                "final_card": None,
            }
        return audit_id

    def log_call(self, audit_id, round_num, mate, model, prompt, response, tokens, duration_ms):
        """记录一次 LLM 调用。在 BaseMate.run 里被调用。"""
        with self._lock:
            session = self._sessions.get(audit_id)
            if session is None:
                raise ValueError(f"unknown audit_id: {audit_id}")
            rounds = session["rounds"]
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append({
                "mate": mate,
                "model": model,
                "prompt": prompt,
                "response": response,
                "tokens": tokens,
                "duration_ms": duration_ms,
                "timestamp": datetime.now().isoformat(),
            })

    def finalize(self, audit_id, final_card):
        """收尾:把内存中的 session 序列化成 JSON 文件,清理内存状态。

        返回写入的文件路径(供调用方记录到决策卡片)。
        """
        with self._lock:
            session = self._sessions.pop(audit_id, None)
            if session is None:
                raise ValueError(f"unknown audit_id: {audit_id}")
            session["final_card"] = final_card
            # 按 round 顺序整理输出
            rounds_list = [
                {"round": k, "calls": session["rounds"][k]}
                for k in sorted(session["rounds"].keys())
            ]
            out = {
                "session_key": session["session_key"],
                "started_at": session["started_at"],
                "finalized_at": datetime.now().isoformat(),
                "rounds": rounds_list,
                "final_card": final_card,
            }
            prefix_safe = _sanitize(session["prefix"])
            key_safe = _sanitize(session["session_key"])
            path = self.audit_dir / f"{prefix_safe}_{key_safe}.json"
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(path)
