from pathlib import Path
from flask import Flask, render_template, jsonify

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

    return app
