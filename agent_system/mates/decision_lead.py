from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep


class DecisionLeadMate(BaseMate):
    """决策 Lead — 综合所有 round_1/round_2 报告 + 关键指标。

    raw K 线不需要,核心是 reports + 指标做加权决策。
    """

    def select_fields(self, data_pack):
        return keep(data_pack, ["indicators", "funding"])

    def synthesize(self, data_pack: dict, round_1_reports: list, round_2_debate: dict,
                   audit_logger=None, audit_id=None) -> dict:
        extra = {
            "round_1_reports_json": round_1_reports,
            "round_2_debate_json": round_2_debate,
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=3)
