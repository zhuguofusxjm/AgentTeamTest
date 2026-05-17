"""Read audit JSON files written by AuditLogger to extract per-Mate round-1 views.

Used by retrospective to build attribution: which Mate said what when this
decision was made, so the LLM can identify which Mates were systematically
right or wrong.
"""
import json
import re
from pathlib import Path


def _try_parse(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def read_round_1_mate_views(audit_path: str) -> list:
    p = Path(audit_path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []

    out = []
    for r in data.get("rounds", []):
        if r.get("round") != 1:
            continue
        for call in r.get("calls", []):
            parsed = _try_parse(call.get("response", ""))
            if not isinstance(parsed, dict):
                continue
            view = parsed.get("view")
            if view is None:
                continue
            out.append({
                "mate": call.get("mate"),
                "view": view,
                "confidence": parsed.get("confidence"),
                "evidence": parsed.get("evidence", [])[:3],
            })
    return out
