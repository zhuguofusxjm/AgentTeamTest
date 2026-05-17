from agent_system.mates.base import BaseMate

class DecisionLeadMate(BaseMate):
    def synthesize(self, data_pack: dict, round_1_reports: list, round_2_debate: dict,
                   audit_logger=None, audit_id=None) -> dict:
        """第 3 轮: 综合所有材料,产出决策卡片 (注意输出 schema 与普通 Mate 不同)"""
        extra = {
            "round_1_reports_json": round_1_reports,
            "round_2_debate_json": round_2_debate,
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=3)
