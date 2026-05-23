from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class MacroSentimentMate(BaseMate):
    """宏观情绪 — 跨币种费率 + 自身费率 + 1d/1w 少量 K 线。

    判断整体加密市场 regime(牛/熊/震荡),
    以及当前币与 BTC 的联动性。大盘熊市时即使单币看多也会降仓。
    """

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["funding", "peer_funding", "indicators"])
        klines = data_pack.get("klines") or {}
        # 只需 1d/1w 判大趋势,不需要 1h/4h
        sliced["klines"] = {
            "1d": (klines.get("1d") or [])[-30:],
            "1w": (klines.get("1w") or [])[-12:],
        }
        return sliced
