from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class FundingRateMate(BaseMate):
    """资金费率分析师 — 只需 funding 段 + 跨币种费率。"""

    def select_fields(self, data_pack):
        return keep(data_pack, ["funding", "peer_funding"])
