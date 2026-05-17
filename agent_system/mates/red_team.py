from agent_system.mates.base import BaseMate

class RedTeamMate(BaseMate):
    def run_rebuttal(self, data_pack: dict, round_1_reports: list, majority_view: str,
                     audit_logger=None, audit_id=None):
        """第 2 轮反驳模式: 接收第 1 轮所有 Mate 输出 + 多数派观点"""
        extra = {
            "round_1_reports_json": round_1_reports,
            "majority_view": majority_view,
            "mode": "rebuttal",
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=2)
