import os
import requests

class ServerChanPush:
    def __init__(self, send_key_env: str = "SERVER_CHAN_KEY"):
        self.send_key = os.environ.get(send_key_env, "")
        self.enabled = bool(self.send_key)

    def _post(self, title: str, desp: str):
        if not self.enabled:
            print(f"[push] disabled (no SEND_KEY); title={title}")
            return
        url = f"https://sctapi.ftqq.com/{self.send_key}.send"
        try:
            requests.post(url, data={"title": title[:32], "desp": desp[:32000]}, timeout=15)
        except Exception as e:
            print(f"[push] failed: {e}")

    def _format_card(self, card: dict) -> str:
        if card.get("direction") == "观望":
            return (f"### {card.get('symbol')} 观望\n\n"
                    f"**Confidence:** {card.get('confidence', 0)}\n\n"
                    f"**Evidence:**\n" +
                    "\n".join(f"- {e}" for e in card.get("key_evidence", [])) +
                    "\n\n**Risks:**\n" +
                    "\n".join(f"- {r}" for r in card.get("key_risks", [])))
        return (
            f"### {card.get('symbol')} {card.get('direction')}\n\n"
            f"**Entry:** {card.get('entry_price')} (zone: {card.get('entry_zone')})\n"
            f"**SL:** {card.get('stop_loss')} | **TP:** {card.get('take_profit')}\n"
            f"**RR:** {card.get('risk_reward_ratio')} | **Position:** {card.get('position_size_pct')}%\n"
            f"**Confidence:** {card.get('confidence')}\n\n"
            f"**Evidence:**\n" + "\n".join(f"- {e}" for e in card.get("key_evidence", [])) +
            f"\n\n**Risks:**\n" + "\n".join(f"- {r}" for r in card.get("key_risks", [])) +
            f"\n\n**Plan:** {card.get('execution_plan', '')}"
        )

    def push_scan_results(self, cards: list):
        if not cards:
            return
        title = f"扫描决策 {len(cards)} 个"
        desp = "\n\n---\n\n".join(self._format_card(c) for c in cards)
        self._post(title, desp)

    def push_tracking_update(self, track: dict, card: dict):
        title = f"跟踪 {track.get('symbol')} {card.get('direction', '')}"
        desp = self._format_card(card) + f"\n\n**Track ID:** {track.get('id')}"
        self._post(title, desp)

    def push_chat_decision(self, card: dict):
        title = f"对话决策 {card.get('symbol')} {card.get('direction', '')}"
        self._post(title, self._format_card(card))
