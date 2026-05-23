from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class FundingRateMate(BaseMate):
    """资金费率分析师 — 只需 funding 段 + 跨币种费率。

    切片极简(~1.5K token):只看费率本身和跨币种对比,
    不需要 K 线或持仓数据。判断当前是否"拥挤"(反转风险)。
    """

    def select_fields(self, data_pack):
        return keep(data_pack, ["funding", "peer_funding"])
