from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep, slim_klines


class LiquidityMate(BaseMate):
    """流动性分析师 — 成交量 + OI 增长率,无需 K 线。"""

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["volume"])
        positions = data_pack.get("positions") or {}
        sliced["positions"] = {
            "oi_history": (positions.get("oi_history") or [])[-48:],
        }
        return sliced
