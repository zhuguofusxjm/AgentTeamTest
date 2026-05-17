from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class MacroSentimentMate(BaseMate):
    """宏观情绪 — 跨币种费率 + 自身费率 + 1d/1w 少量 K 线。"""

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["funding", "peer_funding", "indicators"])
        klines = data_pack.get("klines") or {}
        sliced["klines"] = {
            "1d": (klines.get("1d") or [])[-30:],
            "1w": (klines.get("1w") or [])[-12:],
        }
        return sliced
