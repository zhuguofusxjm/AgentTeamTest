import os
import yaml

class ConfigError(Exception):
    pass

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_mate_config(cfg: dict, mate_name: str) -> dict:
    defaults = cfg.get("defaults", {})
    mate_cfg = cfg.get("mates", {}).get(mate_name)
    if mate_cfg is None:
        raise ConfigError(f"Mate '{mate_name}' not in config.mates")
    merged = {**defaults, **mate_cfg}
    return merged

def resolve_provider_key(cfg: dict, provider_name: str) -> str:
    provider = cfg.get("providers", {}).get(provider_name)
    if provider is None:
        raise ConfigError(f"Provider '{provider_name}' not in config.providers")
    env_name = provider.get("api_key_env")
    if not env_name:
        raise ConfigError(f"Provider '{provider_name}' missing api_key_env")
    value = os.environ.get(env_name)
    if not value:
        raise ConfigError(f"Env var '{env_name}' not set")
    return value

def get_enabled_mates_for_mode(cfg: dict, mode: str) -> list[str]:
    """启用优先级: mate.enabled AND mate 在 mode.enabled_mates 列表中"""
    mode_cfg = cfg.get("modes", {}).get(mode)
    if mode_cfg is None:
        raise ConfigError(f"Mode '{mode}' not in config.modes")
    mode_list = mode_cfg.get("enabled_mates", [])
    mates_cfg = cfg.get("mates", {})
    return [m for m in mode_list if mates_cfg.get(m, {}).get("enabled", False)]
