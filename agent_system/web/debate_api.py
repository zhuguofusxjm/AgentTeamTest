import json
from pathlib import Path
from flask import Blueprint, jsonify, current_app

bp = Blueprint("debate", __name__)

def init_debate_api(audit_dir):
    @bp.route("/api/debate/<int:decision_id>")
    def get_debate(decision_id):
        from agent_system.data.decisions_store import get_decision
        db_path = current_app.config["DB_PATH"]
        d = get_decision(db_path, decision_id)
        if not d:
            return jsonify({"error": "not found"}), 404
        audit_path = d.get("audit_path") or ""
        audit_data = None
        if audit_path and Path(audit_path).exists():
            audit_data = json.loads(Path(audit_path).read_text(encoding="utf-8"))
        return jsonify({"decision": d, "audit": audit_data})

    return bp
