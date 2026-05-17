from pathlib import Path
import json
from flask import Flask, render_template, jsonify, request

def create_app(cfg, chat_runner, audit_dir, db_path):
    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    app.config["DB_PATH"] = db_path
    app.config["AUDIT_DIR"] = audit_dir

    from agent_system.web.chat_api import init_chat_api
    from agent_system.web.debate_api import init_debate_api
    app.register_blueprint(init_chat_api(chat_runner))
    app.register_blueprint(init_debate_api(audit_dir))

    @app.route("/")
    def index():
        return render_template("chat.html")

    @app.route("/api/decisions")
    def list_decisions():
        from agent_system.data.decisions_store import list_recent_decisions
        return jsonify(list_recent_decisions(db_path, limit=50))

    @app.route("/api/team")
    def team():
        from agent_system.mates.display_names import DISPLAY_NAMES, PROFILES
        mates_cfg = cfg.get("mates", {})
        out = []
        for mate_id in DISPLAY_NAMES.keys():
            mc = mates_cfg.get(mate_id, {})
            out.append({
                "mate": mate_id,
                "name": DISPLAY_NAMES.get(mate_id, mate_id),
                "enabled": bool(mc.get("enabled", False)),
                "model": mc.get("model"),
                **PROFILES.get(mate_id, {}),
            })
        return jsonify(out)

    @app.route("/api/tracks")
    def list_tracks():
        from agent_system.data.tracking_store import get_active_tracks
        return jsonify(get_active_tracks(db_path))

    @app.route("/api/track", methods=["POST"])
    def create_track():
        body = request.get_json(force=True) or {}
        decision_id = body.get("decision_id")
        if not decision_id:
            return jsonify({"error": "decision_id required"}), 400
        from agent_system.data.decisions_store import get_decision
        from agent_system.data.tracking_store import add_tracked_position, get_active_tracks
        d = get_decision(db_path, decision_id)
        if not d:
            return jsonify({"error": "decision not found"}), 404
        card = json.loads(d.get("card_json") or "{}")
        direction = card.get("direction") or d.get("direction")
        if direction not in ("多", "空"):
            return jsonify({"error": f"direction='{direction}' 不可跟踪 (仅多/空)"}), 400
        for t in get_active_tracks(db_path):
            if t.get("symbol") == d.get("symbol"):
                return jsonify({
                    "error": f"{d.get('symbol')} 已有活跃跟踪 (id={t.get('id')})",
                    "track_id": t.get("id"),
                }), 409
        track_id = add_tracked_position(
            db_path,
            symbol=d.get("symbol"),
            direction=direction,
            entry_price=card.get("entry_price"),
            stop_loss=card.get("stop_loss"),
            take_profit=card.get("take_profit"),
            entry_signals=f"decision_{decision_id}",
            notes=card.get("execution_plan", "")[:500],
        )
        return jsonify({"track_id": track_id, "symbol": d.get("symbol"), "direction": direction})

    @app.route("/api/tracks/<int:track_id>", methods=["DELETE"])
    def cancel_track(track_id):
        from agent_system.data.tracking_store import get_active_tracks, close_tracked_position
        active = {t["id"]: t for t in get_active_tracks(db_path)}
        if track_id not in active:
            return jsonify({"error": "track not found or already closed"}), 404
        close_tracked_position(db_path, track_id, reason="manual")
        return jsonify({"track_id": track_id, "status": "closed"})

    return app
