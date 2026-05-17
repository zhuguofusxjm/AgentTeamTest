from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class PositionMgrMate(BaseMate):
    """仓位管理 — 基于其他 Mate 输出 + 指标 + 当前价。"""

    def select_fields(self, data_pack):
        return keep(data_pack, ["indicators", "funding"])
