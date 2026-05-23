from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class SmcStructureMate(BaseMate):
    """结构师 — Smart Money Concepts (BOS/CHoCH/OB/FVG/EQH-EQL/Premium-Discount)。

    数据切片策略:只取 data_pack["smc"](已在 data_packer 中预计算好的 4h/1d 结构),
    不需要原始 K 线。这样 prompt 只有 ~4K token。
    """

    def select_fields(self, data_pack):
        # keep() 保留 symbol/timestamp/price_now/tags 作为上下文锚点
        sliced = keep(data_pack, [])
        # 只注入 smc 预计算结果,不传 klines/positions/funding 等
        sliced["smc"] = data_pack.get("smc") or {}
        return sliced
