import json
import os
import uuid
from datetime import datetime
from pathlib import Path

class AuditLogger:
    def __init__(self, audit_dir: str):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._sessions = {}

    def start_session(self, prefix: str, session_key: str) -> str:
        audit_id = str(uuid.uuid4())
        self._sessions[audit_id] = {
            "prefix": prefix,
            "session_key": session_key,
            "started_at": datetime.now().isoformat(),
            "rounds": {},
            "final_card": None,
        }
        return audit_id

    def log_call(self, audit_id, round_num, mate, model, prompt, response, tokens, duration_ms):
        session = self._sessions[audit_id]
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
        session = self._sessions.pop(audit_id)
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
        path = self.audit_dir / f"{session['prefix']}_{session['session_key']}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
