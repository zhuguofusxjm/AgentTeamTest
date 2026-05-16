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

def test_enabled_mates_filters_by_both_mate_enabled_and_mode_list(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
mates:
  m1: { enabled: true, model: x }
  m2: { enabled: false, model: x }
  m3: { enabled: true, model: x }
modes:
  full: { enabled_mates: [m1, m2] }
""")
    from agent_system.core.config_loader import get_enabled_mates_for_mode
    cfg = load_config(str(cfg_file))
    # m2 enabled=false 被过滤; m3 不在 mode list 被过滤; 只剩 m1
    assert get_enabled_mates_for_mode(cfg, "full") == ["m1"]

def test_enabled_mates_unknown_mode_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("modes: {full: {enabled_mates: []}}\n")
    from agent_system.core.config_loader import get_enabled_mates_for_mode
    cfg = load_config(str(cfg_file))
    with pytest.raises(ConfigError):
        get_enabled_mates_for_mode(cfg, "nonexistent")

def test_get_mate_config_unknown_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("mates: {a: {model: x, enabled: true}}\n")
    from agent_system.core.config_loader import get_mate_config
    cfg = load_config(str(cfg_file))
    with pytest.raises(ConfigError):
        get_mate_config(cfg, "unknown")

def test_resolve_provider_key_unknown_provider_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("providers: {}\n")
    from agent_system.core.config_loader import resolve_provider_key
    cfg = load_config(str(cfg_file))
    with pytest.raises(ConfigError):
        resolve_provider_key(cfg, "unknown")

def test_resolve_provider_key_missing_env_field_raises(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("providers: {p1: {base_url: x}}\n")
    from agent_system.core.config_loader import resolve_provider_key
    cfg = load_config(str(cfg_file))
    with pytest.raises(ConfigError):
        resolve_provider_key(cfg, "p1")
