"""Mate 类注册中心 + Orchestrator 装配。

新增 mate 的步骤(以 smc_structure 为例):
  1. 在 mates/ 下写 SmcStructureMate 类
  2. 在 prompts/ 下写 prompt 模板
  3. 在 register_mate_classes() 里 import + 加入 MATE_CLASSES
  4. 在 config.yaml 的 mates 段加配置 + modes 段加入 enabled_mates
  5. 在 mates/display_names.py 加中文名映射
"""
from agent_system.core.config_loader import get_mate_config
from agent_system.core.audit_logger import AuditLogger
from agent_system.core.orchestrator import Orchestrator

# mate_id -> 类。延迟到 register_mate_classes() 才填充,避免循环导入
MATE_CLASSES = {}

def register_mate_classes():
    """注册所有 mate 类到 MATE_CLASSES。

    幂等:重复调用不会重复注册。
    返回 MATE_CLASSES 引用,便于直接查询。
    """
    if MATE_CLASSES:
        return MATE_CLASSES
    # 延迟 import 避免循环依赖(mate 内部可能反向引用 core)
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
    from agent_system.mates.smc_structure import SmcStructureMate
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
        "smc_structure": SmcStructureMate,
    })
    return MATE_CLASSES

def build_orchestrator(cfg, llm, prompts_dir, audit_dir):
    """实例化所有 mate + 组装 Orchestrator。

    特殊处理:
    - red_team 和 decision_lead 不进 mates dict,它们在 Orchestrator 里
      作为独立成员(因为它们的执行时机和方式不同于普通 mate)
    - experience 需要额外的 db_path 参数(其他 mate 不需要)
    """
    register_mate_classes()
    audit = AuditLogger(audit_dir=audit_dir)
    mates = {}            # 普通 mate 字典(在 Round 1 Batch 1 并行执行)
    red_team = None       # 蒋军(独立角色,Round 1 + Round 2 反驳)
    decision_lead = None  # 决策长(Round 3 综合)
    for name, cls in MATE_CLASSES.items():
        mate_cfg = get_mate_config(cfg, name)
        # experience 要查经验库,需要 db_path
        if name == "experience":
            instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg,
                            prompts_dir=prompts_dir, db_path=cfg["data_db"])
        else:
            instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg, prompts_dir=prompts_dir)
        # 按角色分组装入 Orchestrator
        if name == "red_team":
            red_team = instance
        elif name == "decision_lead":
            decision_lead = instance
        else:
            mates[name] = instance
    return Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=red_team,
                        decision_lead=decision_lead, audit_logger=audit)
