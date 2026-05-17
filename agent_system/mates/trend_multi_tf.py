from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep, slim_klines


class TrendMultiTfMate(BaseMate):
    """多周期趋势分析师 — 看 1h/4h/1d/1w 的最近 K 线 + 指标。"""

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["indicators"])
        klines = data_pack.get("klines") or {}
        sliced["klines"] = slim_klines(klines, {
            "1h": 48, "4h": 60, "1d": 60, "1w": 26,
        })
        return sliced
