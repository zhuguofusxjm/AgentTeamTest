from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep, slim_klines


class VolatilityMate(BaseMate):
    """波动压缩 — ATR/BB 指标 + 1h 最近 K 线判断收敛。"""

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["indicators"])
        klines = data_pack.get("klines") or {}
        sliced["klines"] = slim_klines(klines, {"1h": 48})
        return sliced
