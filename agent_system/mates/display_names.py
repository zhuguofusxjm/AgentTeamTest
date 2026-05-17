"""Display name mapping for the 11 Mates.

Backend mate identifiers stay English (DB / configs / audit logs depend on them).
Use these only for surfaces a human reads: web UI, follow-up LLM answers.
"""

DISPLAY_NAMES = {
    "trend_multi_tf": "周期师",
    "funding_rate": "费率官",
    "smart_money": "大户雷达",
    "long_short_compare": "多空裁",
    "volatility": "波动官",
    "experience": "复盘官",
    "red_team": "蒋军",
    "macro_sentiment": "宏观官",
    "liquidity": "水位官",
    "position_mgr": "仓位管家",
    "decision_lead": "决策长",
}


def display_name(mate_id: str) -> str:
    return DISPLAY_NAMES.get(mate_id, mate_id)
