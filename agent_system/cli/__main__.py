import argparse
import json
import os
import sys
from pathlib import Path

from agent_system.core.config_loader import load_config, get_mate_config, resolve_provider_key
from agent_system.core.llm_client import LLMClient
from agent_system.core.data_packer import build as build_pack
from agent_system.providers.deepseek import DeepSeekProvider
from agent_system.data.binance_client import BinanceClient

MATE_CLASSES = {}

def _register_mate_classes():
    from agent_system.mates.trend_multi_tf import TrendMultiTfMate
    MATE_CLASSES["trend_multi_tf"] = TrendMultiTfMate

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
    _register_mate_classes()
    cfg = load_config(args.config)
    llm = _build_llm_client(cfg)
    binance = _build_binance(cfg)

    print(f"[1/3] Fetching data for {args.symbol}...")
    pack = build_pack(args.symbol, binance=binance, peer_symbols=args.peers or [])
    print(f"  -> tags: {pack['tags']}")
    print(f"  -> price_now: {pack['price_now']}")

    if args.mate:
        print(f"[2/3] Running mate '{args.mate}'...")
        mate_cfg = get_mate_config(cfg, args.mate)
        if args.model:
            mate_cfg["model"] = args.model
        prompts_dir = Path(args.config).parent / "prompts"
        cls = MATE_CLASSES.get(args.mate)
        if cls is None:
            print(f"ERROR: Mate '{args.mate}' not registered. Available: {list(MATE_CLASSES.keys())}")
            sys.exit(1)
        mate = cls(name=args.mate, llm_client=llm, mate_cfg=mate_cfg, prompts_dir=str(prompts_dir))
        result = mate.run(pack)
        print("[3/3] Result:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Provide --mate or --mode")

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

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
