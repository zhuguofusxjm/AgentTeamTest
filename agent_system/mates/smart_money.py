from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class SmartMoneyMate(BaseMate):
    """聪明钱分析师 — 大户/账户多空比 + 持仓量 + 主买卖。

    切片:持仓比当前值 + 近 48 根历史 + 成交量(含主买卖比)。
    通过大户行为(而非价格形态)识别机构动向。
    """

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["volume"])
        positions = data_pack.get("positions") or {}
        sliced["positions"] = {
            "top_position_ratio_now": positions.get("top_position_ratio_now"),
            "top_account_ratio_now": positions.get("top_account_ratio_now"),
            "global_account_ratio_now": positions.get("global_account_ratio_now"),
            # 近 48 根(2 天)的 OI 和大户比率历史,用于看趋势
            "oi_history": (positions.get("oi_history") or [])[-48:],
            "top_position_ratio_history": (positions.get("top_position_ratio_history") or [])[-48:],
        }
        return sliced
