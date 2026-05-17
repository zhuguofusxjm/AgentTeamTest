import argparse
import json
import os
import sys
from pathlib import Path

from agent_system.core.config_loader import load_config, get_mate_config, resolve_provider_key
from agent_system.core.llm_client import LLMClient
from agent_system.core.data_packer import build as build_pack
from agent_system.core.mate_registry import register_mate_classes, build_orchestrator, MATE_CLASSES
from agent_system.providers.deepseek import DeepSeekProvider
from agent_system.data.binance_client import BinanceClient

def _build_llm_client(cfg):
    providers = {}
    if "deepseek" in cfg.get("providers", {}):
        key = resolve_provider_key(cfg, "deepseek")
        base_url = cfg["providers"]["deepseek"].get("base_url", "https://api.deepseek.com")
        providers["deepseek"] = DeepSeekProvider(api_key=key, base_url=base_url)
    return LLMClient(cfg, providers=providers)

def _build_binance(cfg):
    bcfg = cfg.get("binance", {})
    api_key = os.environ.get(bcfg.get("api_key_env", "")) if bcfg.get("api_key_env") else None
    api_secret = os.environ.get(bcfg.get("api_secret_env", "")) if bcfg.get("api_secret_env") else None
    return BinanceClient(api_key=api_key, api_secret=api_secret)

def cmd_dry_run(args):
    register_mate_classes()
    cfg = load_config(args.config)
    llm = _build_llm_client(cfg)
    binance = _build_binance(cfg)
    prompts_dir = str(Path(args.config).parent / "prompts")
    audit_dir = cfg.get("audit_dir", "tracks/")

    print(f"[1/3] Fetching data for {args.symbol}...")
    pack = build_pack(args.symbol, binance=binance, peer_symbols=args.peers or [])
    print(f"  -> tags: {pack['tags']}, price_now: {pack['price_now']}")

    if args.mate:
        mate_cfg = get_mate_config(cfg, args.mate)
        if args.model:
            mate_cfg["model"] = args.model
        cls = MATE_CLASSES.get(args.mate)
        if cls is None:
            print(f"ERROR: Mate '{args.mate}' not registered.")
            sys.exit(1)
        mate = cls(name=args.mate, llm_client=llm, mate_cfg=mate_cfg, prompts_dir=prompts_dir)
        print(f"[2/3] Running mate '{args.mate}'...")
        result = mate.run(pack)
        print("[3/3] Result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.mode:
        orch = build_orchestrator(cfg, llm, prompts_dir, audit_dir)
        print(f"[2/3] Running orchestrator mode='{args.mode}'...")
        card = orch.run(symbol=args.symbol, mode=args.mode, data_pack=pack)
        print("[3/3] Decision card:")
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print("Provide --mate or --mode")

def cmd_retro(args):
    cfg = load_config(args.config)
    llm = _build_llm_client(cfg)
    binance = _build_binance(cfg)
    from agent_system.runners.retrospective_runner import RetrospectiveRunner
    runner = RetrospectiveRunner(cfg=cfg, llm_client=llm, db_path=cfg["data_db"], binance=binance)
    runner.run_daily()
    print("done")

def main():
    parser = argparse.ArgumentParser(prog="agent_system.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dry = sub.add_parser("dry_run")
    p_dry.add_argument("--symbol", required=True)
    p_dry.add_argument("--mate", default=None)
    p_dry.add_argument("--mode", default=None)
    p_dry.add_argument("--model", default=None)
    p_dry.add_argument("--peers", nargs="*", default=["BTCUSDT"])
    p_dry.add_argument("--config", default="agent_system/config.yaml")
    p_dry.set_defaults(func=cmd_dry_run)

    p_retro = sub.add_parser("retrospective")
    p_retro.add_argument("--config", default="agent_system/config.yaml")
    p_retro.set_defaults(func=cmd_retro)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
