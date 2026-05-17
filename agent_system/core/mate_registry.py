from agent_system.core.config_loader import get_mate_config
from agent_system.core.audit_logger import AuditLogger
from agent_system.core.orchestrator import Orchestrator

MATE_CLASSES = {}

def register_mate_classes():
    if MATE_CLASSES:
        return MATE_CLASSES
    from agent_system.mates.trend_multi_tf import TrendMultiTfMate
    from agent_system.mates.funding_rate import FundingRateMate
    from agent_system.mates.smart_money import SmartMoneyMate
    from agent_system.mates.long_short_compare import LongShortCompareMate
    from agent_system.mates.volatility import VolatilityMate
    from agent_system.mates.experience import ExperienceMate
    from agent_system.mates.red_team import RedTeamMate
    from agent_system.mates.macro_sentiment import MacroSentimentMate
    from agent_system.mates.liquidity import LiquidityMate
    from agent_system.mates.position_mgr import PositionMgrMate
    from agent_system.mates.decision_lead import DecisionLeadMate
    MATE_CLASSES.update({
        "trend_multi_tf": TrendMultiTfMate,
        "funding_rate": FundingRateMate,
        "smart_money": SmartMoneyMate,
        "long_short_compare": LongShortCompareMate,
        "volatility": VolatilityMate,
        "experience": ExperienceMate,
        "red_team": RedTeamMate,
        "macro_sentiment": MacroSentimentMate,
        "liquidity": LiquidityMate,
        "position_mgr": PositionMgrMate,
        "decision_lead": DecisionLeadMate,
    })
    return MATE_CLASSES

def build_orchestrator(cfg, llm, prompts_dir, audit_dir):
    register_mate_classes()
    audit = AuditLogger(audit_dir=audit_dir)
    mates = {}
    red_team = None
    decision_lead = None
    for name, cls in MATE_CLASSES.items():
        mate_cfg = get_mate_config(cfg, name)
        if name == "experience":
            instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg,
                            prompts_dir=prompts_dir, db_path=cfg["data_db"])
        else:
            instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg, prompts_dir=prompts_dir)
        if name == "red_team":
            red_team = instance
        elif name == "decision_lead":
            decision_lead = instance
        else:
            mates[name] = instance
    return Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=red_team,
                        decision_lead=decision_lead, audit_logger=audit)
