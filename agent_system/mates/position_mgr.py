from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class PositionMgrMate(BaseMate):
    """仓位管理 — 基于其他 Mate 输出 + 指标 + 当前价。

    不判方向,只做"执行层":接收 round_1 所有 mate 的 view,
    用 ATR 算止损距离,用 confidence 加权算仓位大小。
    在 Round 1 Batch 2 执行(等其他 mate 都出结果后)。
    """

    def select_fields(self, data_pack):
        # 只需 ATR(算止损距离)和 funding(判费率成本)
        return keep(data_pack, ["indicators", "funding"])
