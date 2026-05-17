from agent_system.mates.base import BaseMate
from agent_system.core.data_slice import keep, slim_klines


class RedTeamMate(BaseMate):
    """蒋军 — 第 1 轮独立列风险 / 第 2 轮反驳多数派。

    需要看到 raw 数据找漏洞,但只要近期。
    """

    def select_fields(self, data_pack):
        sliced = keep(data_pack, ["funding", "indicators", "volume"])
        positions = data_pack.get("positions") or {}
        sliced["positions"] = {
            "top_position_ratio_now": positions.get("top_position_ratio_now"),
            "top_account_ratio_now": positions.get("top_account_ratio_now"),
            "global_account_ratio_now": positions.get("global_account_ratio_now"),
            "oi_history": (positions.get("oi_history") or [])[-48:],
        }
        klines = data_pack.get("klines") or {}
        sliced["klines"] = slim_klines(klines, {"1h": 48, "4h": 30, "1d": 30})
        return sliced

    def run_rebuttal(self, data_pack: dict, round_1_reports: list, majority_view: str,
                     audit_logger=None, audit_id=None):
        extra = {
            "round_1_reports_json": round_1_reports,
            "majority_view": majority_view,
            "mode": "rebuttal",
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=2)
