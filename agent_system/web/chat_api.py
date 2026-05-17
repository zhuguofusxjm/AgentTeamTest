import json
import queue
import threading
import uuid
from flask import Blueprint, request, jsonify, Response

_session_queues = {}

def init_chat_api(chat_runner):
    bp = Blueprint("chat", __name__)

    @bp.route("/api/chat", methods=["POST"])
    def chat():
        body = request.get_json(force=True)
        session_id = body.get("session_id") or str(uuid.uuid4())
        text = body["text"]
        q = _session_queues.setdefault(session_id, queue.Queue())

        def on_stage(name, payload):
            q.put({"stage": name, "payload": payload})

        def _bg():
            try:
                result = chat_runner.handle_message(session_id, text, on_stage=on_stage)
                q.put({"stage": "done", "payload": result})
            except Exception as e:
                q.put({"stage": "error", "payload": {"error": str(e)}})

        threading.Thread(target=_bg, daemon=True).start()
        return jsonify({"session_id": session_id})

    @bp.route("/api/chat/stream/<session_id>")
    def stream(session_id):
        def gen():
            q = _session_queues.setdefault(session_id, queue.Queue())
            while True:
                try:
                    evt = q.get(timeout=120)
                except queue.Empty:
                    yield "event: heartbeat\ndata: {}\n\n"
                    continue
                yield f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
                if evt.get("stage") in ("done", "error"):
                    break

        return Response(gen(), mimetype="text/event-stream")

    return bp
