from agent_system.mates.base import BaseMate
from agent_system.data.experience_store import search_by_tags

class ExperienceMate(BaseMate):
    def __init__(self, *args, db_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = db_path

    def run(self, data_pack, extra_ctx=None, audit_logger=None, audit_id=None, round_num=1):
        tags = data_pack.get("tags", [])
        retrieved = search_by_tags(self.db_path, query_tags=tags, limit=5, days=90) if self.db_path else []
        if not retrieved:
            return {"mate": "experience", "view": "观望", "confidence": 0,
                    "evidence": ["经验库尚未有匹配场景"],
                    "extra": {"similar_cases": [], "_hit_count": 0}}
        merged_extra = dict(extra_ctx or {})
        merged_extra["retrieved_experiences_json"] = retrieved
        result = super().run(data_pack, extra_ctx=merged_extra,
                              audit_logger=audit_logger, audit_id=audit_id, round_num=round_num)
        if "extra" not in result or not isinstance(result.get("extra"), dict):
            result["extra"] = {}
        result["extra"]["_hit_count"] = len(retrieved)
        return result
