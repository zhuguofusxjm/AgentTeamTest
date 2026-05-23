from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep, slim_klines


class VolatilityMate(BaseMate):
    """波动压缩 — ATR/BB 指标 + 1h 最近 K 线判断收敛。

    不判方向,只判"是否蓄力"(breakout_imminent)。
    当 bb_width_pct < 25 或 atr_12h/atr_7d < 0.4 时给出压缩信号。
    """

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["indicators"])
        klines = data_pack.get("klines") or {}
        # 只需 1h 近 48 根,看近期高低点是否收敛
        sliced["klines"] = slim_klines(klines, {"1h": 48})
        return sliced
