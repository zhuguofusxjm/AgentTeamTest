import json
import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")

def _sanitize(s: str) -> str:
    if not isinstance(s, str):
        return "unknown"
    cleaned = _SAFE_RE.sub("_", s)
    # collapse any remaining ".." sequences to avoid path-traversal in name
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    return cleaned or "unknown"

class AuditLogger:
    def __init__(self, audit_dir: str):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._sessions = {}
        self._lock = threading.Lock()

    def start_session(self, prefix: str, session_key: str) -> str:
        audit_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[audit_id] = {
                "prefix": prefix,
                "session_key": session_key,
                "started_at": datetime.now().isoformat(),
                "rounds": {},
                "final_card": None,
            }
        return audit_id

    def log_call(self, audit_id, round_num, mate, model, prompt, response, tokens, duration_ms):
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
        with self._lock:
            session = self._sessions.pop(audit_id, None)
            if session is None:
                raise ValueError(f"unknown audit_id: {audit_id}")
            session["final_card"] = final_card
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
