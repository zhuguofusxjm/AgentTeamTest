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
        """决策列表(分页+多条件搜索)。"""
        from agent_system.data.decisions_store import list_decisions_paginated
        trigger_mode = request.args.get("trigger_mode") or None
        symbol = request.args.get("symbol") or None
        direction = request.args.get("direction") or None
        status = request.args.get("status") or None
        confidence_min = request.args.get("confidence_min")
        confidence_min = int(confidence_min) if confidence_min else None
        date_start = request.args.get("date_start") or None
        date_end = request.args.get("date_end") or None
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        return jsonify(list_decisions_paginated(
            db_path, page=page, page_size=page_size,
            trigger_mode=trigger_mode, symbol=symbol,
            direction=direction, status=status,
            confidence_min=confidence_min,
            date_start=date_start, date_end=date_end,
        ))

    @app.route("/api/status")
    def system_status():
        """顶部状态栏数据。

        返回:
        - decisions: 决策汇总统计(按 trigger_mode 分组 + open/win/loss)
        - active_tracks: 活跃跟踪数
        - dependencies: API 依赖健康(deepseek_key / binance_key 是否配好)
        - server_time: 服务器当前时间
        """
        import os
        from datetime import datetime
        from agent_system.data.decisions_store import count_decisions_summary
        from agent_system.data.tracking_store import get_active_tracks

        deepseek_env = cfg.get("providers", {}).get("deepseek", {}).get("api_key_env", "")
        binance_env = cfg.get("binance", {}).get("api_key_env", "")
        return jsonify({
            "decisions": count_decisions_summary(db_path),
            "active_tracks": len(get_active_tracks(db_path)),
            "dependencies": {
                "deepseek_key": bool(os.environ.get(deepseek_env)) if deepseek_env else False,
                "binance_key": bool(os.environ.get(binance_env)) if binance_env else False,
            },
            "server_time": datetime.now().isoformat(timespec="seconds"),
        })

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
