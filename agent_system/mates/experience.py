from agent_system.mates.base import BaseMate
from agent_system.data.experience_store import search_by_tags

class ExperienceMate(BaseMate):
    """复盘官 — 按场景 tags 检索经验库,提供历史胜负参考。

    特殊流程:先查 SQLite 经验库,有匹配结果才调 LLM 总结;
    无结果直接返回 confidence=0,不浪费 token。
    默认停用(enabled: false),经验库 30 条以上才建议启用。
    """

    def __init__(self, *args, db_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = db_path

    def select_fields(self, data_pack):
        # 只需 symbol 和 tags(用于检索),不需要任何市场数据
        return {
            "symbol": data_pack.get("symbol"),
            "tags": data_pack.get("tags") or [],
        }

    def run(self, data_pack, extra_ctx=None, audit_logger=None, audit_id=None, round_num=1):
        """先查库再决定是否调 LLM。"""
        tags = data_pack.get("tags", [])
        # 按 tags 匹配近 90 天的历史经验,最多取 5 条
        retrieved = search_by_tags(self.db_path, query_tags=tags, limit=5, days=90) if self.db_path else []
        if not retrieved:
            # 无匹配经验,直接返回空结果,不调 LLM
            return {"mate": "experience", "view": "观望", "confidence": 0,
                    "evidence": ["经验库尚未有匹配场景"],
                    "extra": {"similar_cases": [], "_hit_count": 0}}
        # 有匹配结果,把检索结果注入 prompt 让 LLM 总结
        merged_extra = dict(extra_ctx or {})
        merged_extra["retrieved_experiences_json"] = retrieved
        result = super().run(data_pack, extra_ctx=merged_extra,
                              audit_logger=audit_logger, audit_id=audit_id, round_num=round_num)
        if "extra" not in result or not isinstance(result.get("extra"), dict):
            result["extra"] = {}
        result["extra"]["_hit_count"] = len(retrieved)
        return result
