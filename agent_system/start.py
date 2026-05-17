import os
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent_system.core.config_loader import load_config, get_mate_config, resolve_provider_key
from agent_system.core.llm_client import LLMClient
from agent_system.core.data_packer import build as build_pack
from agent_system.core.audit_logger import AuditLogger
from agent_system.core.orchestrator import Orchestrator
from agent_system.providers.deepseek import DeepSeekProvider
from agent_system.data.binance_client import BinanceClient
from agent_system.data.db import init_new_tables
from agent_system.runners.chat_runner import ChatRunner
from agent_system.runners.scan_runner import ScanRunner
from agent_system.runners.tracking_runner import TrackingRunner
from agent_system.push.server_chan import ServerChanPush
from agent_system.web.app import create_app

CONFIG_PATH = "agent_system/config.yaml"
_stop_flag = threading.Event()

def _build_orchestrator(cfg, llm, prompts_dir, audit_dir):
    from agent_system.cli.__main__ import _register_mate_classes, MATE_CLASSES
    _register_mate_classes()
    audit = AuditLogger(audit_dir=audit_dir)
    mates = {}
    red_team = None
    decision_lead = None
    for name, cls in MATE_CLASSES.items():
        mate_cfg = get_mate_config(cfg, name)
        instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg, prompts_dir=prompts_dir)
        if name == "red_team":
            red_team = instance
        elif name == "decision_lead":
            decision_lead = instance
        else:
            mates[name] = instance
    return Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=red_team,
                        decision_lead=decision_lead, audit_logger=audit)

def _scan_loop(scan_runner, interval_min):
    while not _stop_flag.is_set():
        try:
            scan_runner.run_once()
        except Exception as e:
            print(f"[scan_loop] {e}")
        _stop_flag.wait(interval_min * 60)

def _tracking_loop(tracking_runner, interval_min):
    while not _stop_flag.is_set():
        try:
            tracking_runner.run_once()
        except Exception as e:
            print(f"[tracking_loop] {e}")
        _stop_flag.wait(interval_min * 60)

def main():
    cfg = load_config(CONFIG_PATH)
    db_path = cfg["data_db"]
    audit_dir = cfg["audit_dir"]
    prompts_dir = "agent_system/prompts"

    Path(audit_dir).mkdir(parents=True, exist_ok=True)
    init_new_tables(db_path)

    deepseek_key = resolve_provider_key(cfg, "deepseek")
    base_url = cfg["providers"]["deepseek"].get("base_url", "https://api.deepseek.com")
    providers = {"deepseek": DeepSeekProvider(api_key=deepseek_key, base_url=base_url)}
    llm = LLMClient(cfg, providers=providers)

    bcfg = cfg.get("binance", {})
    binance = BinanceClient(
        api_key=os.environ.get(bcfg.get("api_key_env", "")),
        api_secret=os.environ.get(bcfg.get("api_secret_env", "")),
    )

    push_key_env = cfg.get("push", {}).get("server_chan", {}).get("key_env", "SERVER_CHAN_KEY")
    push = ServerChanPush(send_key_env=push_key_env)

    orch = _build_orchestrator(cfg, llm, prompts_dir, audit_dir)

    chat_runner = ChatRunner(cfg=cfg, llm_client=llm, orchestrator=orch,
                             binance=binance, db_path=db_path, data_packer=build_pack)
    scan_runner = ScanRunner(cfg=cfg, llm_client=llm, orchestrator=orch,
                             binance=binance, db_path=db_path, data_packer=build_pack,
                             push_client=push)
    tracking_runner = TrackingRunner(cfg=cfg, llm_client=llm, orchestrator=orch,
                                     binance=binance, db_path=db_path,
                                     data_packer=build_pack, push_client=push)

    sched = cfg.get("scheduler", {})
    threading.Thread(target=_scan_loop, args=(scan_runner, sched.get("scan_interval_min", 30)),
                     daemon=True).start()
    threading.Thread(target=_tracking_loop, args=(tracking_runner, sched.get("tracking_interval_min", 15)),
                     daemon=True).start()

    app = create_app(cfg, chat_runner, audit_dir, db_path)

    def _stop(signum, frame):
        print("[start] shutting down...")
        _stop_flag.set()
        sys.exit(0)
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    print("[start] Web on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

if __name__ == "__main__":
    main()
