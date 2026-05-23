from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class LongShortCompareMate(BaseMate):
    """多空对比 — 仅 3 个比率当前值,极简。

    全团队最轻量的 mate(~800 token)。
    只做一件事:量化大户 vs 散户的方向分歧程度。
    """

    def select_fields(self, data_pack):
        sliced = keep(data_pack, [])
        positions = data_pack.get("positions") or {}
        sliced["positions"] = {
            "top_position_ratio_now": positions.get("top_position_ratio_now"),
            "top_account_ratio_now": positions.get("top_account_ratio_now"),
            "global_account_ratio_now": positions.get("global_account_ratio_now"),
        }
        return sliced
