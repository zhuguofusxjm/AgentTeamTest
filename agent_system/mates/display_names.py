"""Display name + role description for the 11 Mates.

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
    "red_team": "投资风险师",
    "macro_sentiment": "宏观官",
    "liquidity": "水位官",
    "position_mgr": "仓位管家",
    "decision_lead": "决策长",
    "smc_structure": "结构师",
}

PROFILES = {
    "trend_multi_tf": {
        "role": "多周期趋势分析师",
        "focus": "1h / 4h / 1d / 1w 多周期协同",
        "signals": "EMA 20/50/200 排列、MACD 近似、K 线突破/跌破",
        "output": "view + cycle_summary 各周期一句话 + alignment(一致/分歧)",
    },
    "funding_rate": {
        "role": "资金费率分析师",
        "focus": "费率绝对值 + 30 天分位 + 跨币种对比",
        "signals": "> 0.0010 极端拥挤; < -0.0010 反向极端; 与 BTC/SOL 差异",
        "output": "view + risk_flag(拥挤/正常)",
    },
    "smart_money": {
        "role": "聪明钱分析师",
        "focus": "大户/账户多空比 + 持仓量变化 + 主买卖",
        "signals": "top_position_ratio 极端、OI 增长、taker_buy_ratio 偏离",
        "output": "view + smart_money_direction(多/空/中性)",
    },
    "long_short_compare": {
        "role": "多空对比分析师",
        "focus": "大户多空比 vs 全市场多空比的背离",
        "signals": "差值 > 0.8 强背离, 散户被收割概率高",
        "output": "view + divergence_score (0-100)",
    },
    "volatility": {
        "role": "波动压缩分析师",
        "focus": "ATR 比值 + 布林带带宽分位 + 收敛形态",
        "signals": "atr_12h/atr_7d < 0.4; bb_width_pct < 25 严重压缩",
        "output": "view (通常观望) + breakout_imminent (true/false)",
    },
    "experience": {
        "role": "经验复盘分析师",
        "focus": "按场景 tags 检索历史经验库",
        "signals": "近 90 天匹配 tag 的胜负记录 + lesson",
        "output": "view + similar_cases (历史样本)",
    },
    "red_team": {
        "role": "投资风险师",
        "focus": "对立面视角 — 列出最可能让人亏钱的 3 条路径",
        "signals": "第 1 轮独立列风险; 第 2 轮反驳多数派核心论据",
        "output": "view + counterview + risks[] + black_swan_scenarios",
    },
    "macro_sentiment": {
        "role": "宏观情绪分析师",
        "focus": "BTC 主导率 + 跨币种联动 + 大盘 regime",
        "signals": "1d/1w 周期 BTC 走势 + 当前币与 BTC 同步性",
        "output": "view + market_regime (牛/熊/震荡)",
    },
    "liquidity": {
        "role": "流动性分析师",
        "focus": "成交量放大/萎缩 + 持仓量变化 + 主买卖均衡",
        "signals": "recent_24h vs ma_7d; OI 增长率;主买/卖极端",
        "output": "view + liquidity_health (好/一般/差)",
    },
    "position_mgr": {
        "role": "仓位管家",
        "focus": "综合其他 Mate 的方向 + ATR 算止损/止盈/仓位",
        "signals": "atr_12h × 1.5 短线止损;RR ≥ 2;confidence 加权仓位",
        "output": "entry_price + stop_loss + take_profit + position_size_pct",
    },
    "decision_lead": {
        "role": "决策长",
        "focus": "综合三轮辩论(独立 → 反驳 → 综合)产出最终决策卡片",
        "signals": "多 Mate 共识 + 蒋军反驳后的 confidence 加权",
        "output": "完整决策卡片(direction/entry/SL/TP/key_evidence/key_risks/plan)",
    },
    "smc_structure": {
        "role": "SMC 结构师",
        "focus": "4h / 1d 的 BOS/CHoCH 趋势 + Order Block / FVG / EQH-EQL 关键价位",
        "signals": "swing 破位 (CHoCH 反转 / BOS 延续);未失效 OB & FVG 的距离;trailing 区间内的 Premium / Discount 位置",
        "output": "view + structure_bias_4h/1d + last_event_summary + key_levels + zone_4h/1d",
    },
}


def display_name(mate_id: str) -> str:
    return DISPLAY_NAMES.get(mate_id, mate_id)


def profile(mate_id: str) -> dict:
    return PROFILES.get(mate_id) or {}

