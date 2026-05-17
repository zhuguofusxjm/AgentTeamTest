import json
import re
from agent_system.data.chat_store import save_message, list_messages
from agent_system.data.decisions_store import save_decision, get_decision
from agent_system.core.audit_reader import read_round_1_mate_views
from agent_system.mates.display_names import display_name

INTENT_PROMPT = """你是意图解析器。识别用户消息的意图,输出 JSON。

可选意图:
- single_analysis: 用户希望分析某个币种的入场机会(消息里出现了具体币种或合约名)
- follow_up: 用户在追问刚刚讨论的决策(例如:"你们有几个分析师参与?各自的观点是什么?为什么这样判断?有什么风险?"等),且对话历史里**已有过一次决策**
- tracking_query: 用户询问已跟踪的持仓
- data_query: 用户询问某币种的简单数据(费率/价格等)
- chitchat: 闲聊或不属于以上

判断 follow_up 的关键:
- 对话历史里有过 assistant 发出决策卡片
- 当前消息没有提新币种,而是问"分析师/Mate/各自的观点/为什么/依据/风险/调整"等关于上次决策的细节

输出格式:
{"intent": "<意图>", "symbol": "<币种,无则 null>", "extra": {}}

## 对话历史 (最近 6 条)
{{ history }}

## 当前用户消息
{{ user_text }}"""


FOLLOW_UP_PROMPT = """你是 11 位分析师圆桌的发言人。基于上一次刚做出的决策,自然口语化回答用户的追问。

## 这次决策的背景
- 币种: {symbol}
- 最终方向: {direction} (置信度 {confidence})
- 入场价: {entry_price}, 止损: {stop_loss}, 止盈: {take_profit}
- 关键依据: {key_evidence}
- 关键风险: {key_risks}
- 执行计划: {execution_plan}

## 这次圆桌的 11 位分析师在第 1 轮各自的独立判断
说明: 每条 mate_name 已是中文角色名,直接使用,不要再转译。
{mate_views_json}

## 用户的追问
{user_text}

## 回答要求
- 自然中文,不要用 JSON
- 引用分析师时直接用中文角色名 (例: "蒋军认为...","周期师指出...")。**严禁在回答中出现任何带下划线的英文标识**
- 如果用户问"几个分析师",回答具体数字 + 列出中文角色名 + 各自的 view
- 如果用户问"为什么/依据",从 mate_views 里拣最相关的引用
- 如果用户问"风险",优先讲蒋军(Red Team)的观点
- 如果是其他追问,聚焦回答,不重复讲整张卡片
- 直接回答,不要前缀"好的""根据"等

请回答:"""


def parse_intent(llm_client, model: str, user_text: str, history: list) -> dict:
    history_str = "\n".join(
        f"{m['role']}: {m['content'][:200]}"
        for m in history[-6:]
    ) or "(无历史)"
    prompt = INTENT_PROMPT.replace("{{ user_text }}", user_text).replace("{{ history }}", history_str)
    resp = llm_client.chat(
        model=model, messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=200, response_format="json",
    )
    try:
        m = re.search(r'\{.*\}', resp.text, re.DOTALL)
        return json.loads(m.group(0) if m else resp.text)
    except Exception:
        return {"intent": "chitchat", "symbol": None, "extra": {}}


def _last_decision_id_in_session(db_path, session_id):
    msgs = list_messages(db_path, session_id)
    for m in reversed(msgs):
        if m.get("decision_id"):
            return m["decision_id"]
    return None


class ChatRunner:
    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer

    def _answer_follow_up(self, session_id: str, user_text: str, decision_id: int) -> str:
        decision = get_decision(self.db_path, decision_id)
        if not decision:
            return "找不到上一次决策的记录,要不重新问一下要分析的币种?"
        card = json.loads(decision.get("card_json") or "{}")
        audit_path = decision.get("audit_path") or ""
        mate_views = read_round_1_mate_views(audit_path) if audit_path else []
        for v in mate_views:
            mid = v.get("mate")
            if mid:
                v["mate_name"] = display_name(mid)
                v.pop("mate", None)
        prompt = FOLLOW_UP_PROMPT.format(
            symbol=decision.get("symbol"),
            direction=card.get("direction"),
            confidence=card.get("confidence"),
            entry_price=card.get("entry_price"),
            stop_loss=card.get("stop_loss"),
            take_profit=card.get("take_profit"),
            key_evidence=json.dumps(card.get("key_evidence", []), ensure_ascii=False),
            key_risks=json.dumps(card.get("key_risks", []), ensure_ascii=False),
            execution_plan=card.get("execution_plan", ""),
            mate_views_json=json.dumps(mate_views, ensure_ascii=False, indent=2),
            user_text=user_text,
        )
        model = self.cfg.get("default_model", "deepseek-chat")
        resp = self.llm.chat(
            model=model, messages=[{"role": "user", "content": prompt}],
            temperature=0.5, max_tokens=1000,
        )
        return resp.text.strip()

    def handle_message(self, session_id: str, user_text: str, on_stage=None) -> dict:
        save_message(self.db_path, session_id, "user", user_text)
        history = list_messages(self.db_path, session_id)
        intent_model = self.cfg.get("default_model", "deepseek-chat")
        intent = parse_intent(self.llm, intent_model, user_text, history)

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

        elif intent["intent"] == "follow_up":
            decision_id = _last_decision_id_in_session(self.db_path, session_id)
            if decision_id is None:
                msg = "这个会话还没产生过决策,先告诉我你想分析哪个币?"
                save_message(self.db_path, session_id, "assistant", msg)
                return {"type": "follow_up_answer", "message": msg, "decision_id": None}
            answer = self._answer_follow_up(session_id, user_text, decision_id)
            save_message(self.db_path, session_id, "assistant", answer, decision_id=decision_id)
            return {"type": "follow_up_answer", "message": answer, "decision_id": decision_id}

        elif intent["intent"] == "data_query" and intent.get("symbol"):
            return {"type": "data_query", "intent": intent,
                    "message": f"暂未实现 data_query 详细应答(intent: {intent})"}

        elif intent["intent"] == "tracking_query":
            return {"type": "tracking_query",
                    "message": "持仓跟踪查询(Phase 4 实现)"}

        else:
            return {"type": "chitchat",
                    "message": "我是币安合约智能体,可以帮你分析具体币种(例如:'帮我分析 ETH 是否有买卖点')。"}
