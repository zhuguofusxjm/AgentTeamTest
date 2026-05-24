"""一次性修正脚本:用新的逐根遍历逻辑重新评估所有已关闭(win/loss)的决策。

用法:
  python -m agent_system.scripts.fix_decision_status

会输出每条被修正的决策 ID 和前后状态对比。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent_system.core.config_loader import load_config
from agent_system.data.db import get_conn
from agent_system.data.decisions_store import update_decision_status
from agent_system.runners.decision_status_tracker import DecisionStatusTracker
from agent_system.data.binance_client import BinanceClient


def main():
    cfg = load_config("agent_system/config.yaml")
    db_path = cfg["data_db"]

    bcfg = cfg.get("binance", {})
    api_key = os.environ.get(bcfg.get("api_key_env", "")) if bcfg.get("api_key_env") else None
    api_secret = os.environ.get(bcfg.get("api_secret_env", "")) if bcfg.get("api_secret_env") else None
    binance = BinanceClient(api_key=api_key, api_secret=api_secret)

    tracker = DecisionStatusTracker(db_path=db_path, binance=binance)

    # 查所有已关闭的决策(win/loss/expired)
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM decisions WHERE status IN ('win', 'loss', 'expired')"
    ).fetchall()
    conn.close()

    print(f"共 {len(rows)} 条已关闭决策需要重新评估\n")

    changed = 0
    for r in rows:
        d = dict(r)
        old_status = d["status"]
        old_pnl = d.get("realized_pnl_pct")
        result = tracker._evaluate(d)
        if result is None:
            # 重新评估后认为还没触发(可能数据不足),跳过
            continue
        new_status, new_pnl = result
        if new_status != old_status or (old_pnl and abs(new_pnl - old_pnl) > 0.01):
            update_decision_status(db_path, d["decision_id"],
                                   status=new_status, realized_pnl_pct=new_pnl)
            print(f"  #{d['decision_id']} {d['symbol']}: {old_status}({old_pnl:.2f}%) → {new_status}({new_pnl:.2f}%)")
            changed += 1

    print(f"\n修正完成: {changed}/{len(rows)} 条被更新")


if __name__ == "__main__":
    main()
