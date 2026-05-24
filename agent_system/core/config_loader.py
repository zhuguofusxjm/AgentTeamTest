"""配置加载与查询工具。

封装 config.yaml 的读取 + Mate 配置合并 + 环境变量解析。
"""
import os
import yaml

class ConfigError(Exception):
    """配置缺失或非法时抛出。"""
    pass

def load_config(path: str) -> dict:
    """读取 config.yaml,返回 dict;空文件返回 {}。"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_mate_config(cfg: dict, mate_name: str) -> dict:
    """合并 defaults + mates.<name> 段,得到该 mate 的最终配置。

    优先级:mate 级配置 > defaults 兜底。
    例如 defaults.temperature=0.3,但 trend_multi_tf.temperature=0.2,
    最终 trend_multi_tf 用 0.2。
    """
    defaults = cfg.get("defaults", {})
    mate_cfg = cfg.get("mates", {}).get(mate_name)
    if mate_cfg is None:
        raise ConfigError(f"Mate '{mate_name}' not in config.mates")
    merged = {**defaults, **mate_cfg}
    return merged

def resolve_provider_key(cfg: dict, provider_name: str) -> str:
    """从环境变量读取 provider 的 API key。

    config 里只存 env var 名(api_key_env: DEEPSEEK_API_KEY),实际值从环境读。
    避免 key 写进版本控制。
    """
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
    """启用优先级: mate.enabled AND mate 在 mode.enabled_mates 列表中。

    两者必须都满足:全局 enabled=true,且该模式的列表里包含它。
    例如 experience 默认 enabled=false,即使在 lean.enabled_mates 中也不会跑。
    """
    mode_cfg = cfg.get("modes", {}).get(mode)
    if mode_cfg is None:
        raise ConfigError(f"Mode '{mode}' not in config.modes")
    mode_list = mode_cfg.get("enabled_mates", [])
    mates_cfg = cfg.get("mates", {})
    return [m for m in mode_list if mates_cfg.get(m, {}).get("enabled", False)]
