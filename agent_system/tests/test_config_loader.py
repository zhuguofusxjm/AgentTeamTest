import os
import pytest
from agent_system.core.config_loader import load_config, ConfigError

def test_load_config_returns_dict(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("default_model: deepseek-chat\n")
    cfg = load_config(str(cfg_file))
    assert cfg["default_model"] == "deepseek-chat"

def test_get_mate_with_defaults_fallback(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
defaults:
  temperature: 0.3
  max_tokens: 2000
mates:
  m1:
    model: deepseek-chat
    enabled: true
""")
    from agent_system.core.config_loader import get_mate_config
    cfg = load_config(str(cfg_file))
    m1 = get_mate_config(cfg, "m1")
    assert m1["temperature"] == 0.3
    assert m1["max_tokens"] == 2000
    assert m1["model"] == "deepseek-chat"

def test_resolve_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
providers:
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
""")
    from agent_system.core.config_loader import resolve_provider_key
    cfg = load_config(str(cfg_file))
    assert resolve_provider_key(cfg, "deepseek") == "sk-test"

def test_missing_env_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
providers:
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
""")
    from agent_system.core.config_loader import resolve_provider_key
    cfg = load_config(str(cfg_file))
    with pytest.raises(ConfigError):
        resolve_provider_key(cfg, "deepseek")
