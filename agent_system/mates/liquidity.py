from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep, slim_klines


class LiquidityMate(BaseMate):
    """流动性分析师 — 成交量 + OI 增长率,无需 K 线。

    不判方向,只判信号质量:流动性差时其他 mate 的信号不可靠。
    输出 liquidity_health 供决策长做 confidence 折扣。
    """

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["volume"])
        positions = data_pack.get("positions") or {}
        # 只需 OI 历史(看资金进出),不需要多空比
        sliced["positions"] = {
            "oi_history": (positions.get("oi_history") or [])[-48:],
        }
        return sliced
