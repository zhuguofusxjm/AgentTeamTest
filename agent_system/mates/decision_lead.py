from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class DecisionLeadMate(BaseMate):
    """决策 Lead — 综合所有 round_1/round_2 报告 + 关键指标。

    在 Round 3 执行。不做独立分析,只做"综合裁判":
    把 12 位 mate 的 view/confidence 加权,结合蒋军反驳,
    输出最终决策卡片(direction/entry/SL/TP/evidence/risks/plan)。
    temperature=0.2 确保输出稳定。
    """

    def select_fields(self, data_pack):
        # 只需指标和费率做参考,核心输入是 round_1/round_2 报告(通过 extra_ctx 传入)
        return keep(data_pack, ["indicators", "funding"])

    def synthesize(self, data_pack: dict, round_1_reports: list, round_2_debate: dict,
                   audit_logger=None, audit_id=None) -> dict:
        """Round 3 综合入口:把全部报告注入 prompt,调 LLM 产出决策卡片。"""
        extra = {
            "round_1_reports_json": round_1_reports,
            "round_2_debate_json": round_2_debate,
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=3)
