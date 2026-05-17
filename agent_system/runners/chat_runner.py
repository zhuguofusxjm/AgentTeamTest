import json
import re
from agent_system.data.chat_store import save_message
from agent_system.data.decisions_store import save_decision

INTENT_PROMPT = """你是意图解析器。识别用户消息的意图,输出 JSON。

可选意图:
- single_analysis: 用户希望分析某个币种的入场机会(包含币种或合约名)
- tracking_query: 用户询问已跟踪的持仓
- data_query: 用户询问某币种的简单数据(费率/价格等)
- chitchat: 闲聊或不属于以上

输出格式:
{"intent": "<意图>", "symbol": "<币种.如 ETHUSDT,无则 null>", "extra": {}}

用户消息: {{ user_text }}"""

def parse_intent(llm_client, model: str, user_text: str) -> dict:
    prompt = INTENT_PROMPT.replace("{{ user_text }}", user_text)
    resp = llm_client.chat(
        model=model, messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=200, response_format="json",
    )
    try:
        m = re.search(r'\{.*\}', resp.text, re.DOTALL)
        return json.loads(m.group(0) if m else resp.text)
    except Exception:
        return {"intent": "chitchat", "symbol": None, "extra": {}}

class ChatRunner:
    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer

    def handle_message(self, session_id: str, user_text: str, on_stage=None) -> dict:
        save_message(self.db_path, session_id, "user", user_text)
        intent_model = self.cfg.get("default_model", "deepseek-chat")
        intent = parse_intent(self.llm, intent_model, user_text)

        if on_stage:
            on_stage("intent", intent)

        if intent["intent"] == "single_analysis" and intent.get("symbol"):
            symbol = intent["symbol"]
            if on_stage:
                on_stage("data_packing", {"symbol": symbol})
            pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
            if on_stage:
                on_stage("orchestrator_start", {"symbol": symbol, "mode": "full"})

            def _orch_event(name, payload):
                if on_stage:
                    on_stage(name, payload)

            card = self.orch.run(symbol=symbol, mode="full", data_pack=pack,
                                  on_event=_orch_event)
            tags = pack.get("tags", [])
            audit_path = card.get("audit_path") or ""
            decision_id = save_decision(
                self.db_path, symbol=symbol, trigger_mode="chat",
                card=card, tags=tags, audit_path=audit_path,
            )
            card["decision_id"] = decision_id
            save_message(self.db_path, session_id, "assistant",
                         json.dumps(card, ensure_ascii=False), decision_id=decision_id)
            if on_stage:
                on_stage("decision_card", card)
            return {"type": "decision_card", "card": card}

        elif intent["intent"] == "data_query" and intent.get("symbol"):
            return {"type": "data_query", "intent": intent,
                    "message": f"暂未实现 data_query 详细应答(intent: {intent})"}

        elif intent["intent"] == "tracking_query":
            return {"type": "tracking_query",
                    "message": "持仓跟踪查询(Phase 4 实现)"}

        else:
            return {"type": "chitchat",
                    "message": "我是币安合约智能体,可以帮你分析具体币种(例如:'帮我分析 ETH 是否有买卖点')。"}
