from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class SmartMoneyMate(BaseMate):
    """聪明钱分析师 — 大户/账户多空比 + 持仓量 + 主买卖。"""

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["volume"])
        positions = data_pack.get("positions") or {}
        sliced["positions"] = {
            "top_position_ratio_now": positions.get("top_position_ratio_now"),
            "top_account_ratio_now": positions.get("top_account_ratio_now"),
            "global_account_ratio_now": positions.get("global_account_ratio_now"),
            "oi_history": (positions.get("oi_history") or [])[-48:],
            "top_position_ratio_history": (positions.get("top_position_ratio_history") or [])[-48:],
        }
        return sliced
