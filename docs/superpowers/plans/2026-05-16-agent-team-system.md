# Agent Team 量化分析系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有"信号引擎 + 单次 LLM 诊断"系统重构为 11 Mate 圆桌辩论 + 轻量经验复盘的 Agent Team 系统。

**Architecture:** 全新 `agent_system/` 项目目录，复用现有 SQLite 数据库与采集脚本。三轮辩论编排（独立分析 → 蒋军反驳 → Lead 综合）通过 `core/orchestrator.py` 实现。LLM 抽象层支持多 provider（第一阶段仅 DeepSeek）。三种触发模式（chat/scan/tracking）共用同一 orchestrator，通过模式档位（full/lean/tracking）切换 Mate 列表与轮数。

**Tech Stack:** Python 3.11+ / Flask / SQLite / DeepSeek API / 币安 fapi（签名版） / Server酱 / pytest

---

## 文件结构

```
agent_system/                              # 新项目根目录
├── __init__.py
├── config.yaml                            # Phase 1 创建
├── start.py                               # Phase 3 创建
├── requirements.txt                       # Phase 1 创建
├── README.md                              # Phase 5 完成后
│
├── core/
│   ├── __init__.py
│   ├── config_loader.py                   # 加载 YAML, 回落 defaults, env 解引用
│   ├── llm_client.py                      # LLM 抽象, 按 model 前缀分发
│   ├── audit_logger.py                    # 审计 JSON 落盘
│   ├── data_packer.py                     # DataPack 聚合 + 标签提取
│   └── orchestrator.py                    # 三轮辩论编排, 统一入口
│
├── providers/
│   ├── __init__.py
│   ├── base.py                            # Provider 抽象基类
│   ├── deepseek.py                        # DeepSeek 实现
│   ├── claude.py                          # 接口预留 (raise NotImplementedError)
│   └── openai.py                          # 接口预留 (raise NotImplementedError)
│
├── mates/
│   ├── __init__.py
│   ├── base.py                            # Mate 基类: load prompt, render, call llm, parse JSON
│   ├── trend_multi_tf.py
│   ├── funding_rate.py
│   ├── smart_money.py
│   ├── long_short_compare.py
│   ├── volatility.py
│   ├── experience.py                      # Phase 4 实现, 仍 enabled=false
│   ├── red_team.py                        # 第 1 轮列风险, 第 2 轮反驳
│   ├── macro_sentiment.py
│   ├── liquidity.py
│   ├── position_mgr.py                    # Batch 2 后置, 依赖 Batch 1 输出
│   └── decision_lead.py                   # 系统级, 第 3 轮综合
│
├── prompts/
│   ├── _shared/
│   │   ├── output_schema.md
│   │   ├── data_pack_format.md
│   │   └── role_persona.md
│   ├── trend_multi_tf.md
│   ├── funding_rate.md
│   ├── smart_money.md
│   ├── long_short_compare.md
│   ├── volatility.md
│   ├── experience.md
│   ├── red_team.md
│   ├── macro_sentiment.md
│   ├── liquidity.md
│   ├── position_mgr.md
│   └── decision_lead.md
│
├── runners/
│   ├── __init__.py
│   ├── chat_runner.py                     # 用户对话 + 意图解析
│   ├── scan_runner.py                     # 定时扫描 + 旧 signals.py 预筛
│   ├── tracking_runner.py                 # 持仓跟踪
│   ├── decision_status_tracker.py         # 每 1h 检查 open 决策状态
│   └── retrospective_runner.py            # 每天凌晨复盘
│
├── data/
│   ├── __init__.py
│   ├── db.py                              # 复用旧 db.py + 新增 3 张表 init
│   ├── binance_client.py                  # 币安签名版客户端
│   ├── decisions_store.py                 # decisions 表 CRUD
│   ├── experience_store.py                # experiences 表 CRUD + 标签检索
│   └── chat_store.py                      # chat_messages 表 CRUD
│
├── web/
│   ├── __init__.py
│   ├── app.py                             # Flask app + 路由注册
│   ├── chat_api.py                        # /api/chat POST + /api/sessions
│   ├── debate_api.py                      # /api/debate/<id>/stream SSE
│   ├── scan_api.py                        # /api/scans 最近扫描结果
│   ├── tracking_api.py                    # /api/tracks CRUD
│   ├── static/
│   │   ├── chat.css
│   │   └── chat.js
│   └── templates/
│       └── chat.html                      # 三栏布局
│
├── push/
│   ├── __init__.py
│   └── server_chan.py                     # Server酱 推送
│
├── cli/
│   ├── __init__.py
│   └── __main__.py                        # python -m agent_system.cli
│
└── tests/
    ├── __init__.py
    ├── conftest.py                        # pytest fixtures
    ├── test_config_loader.py
    ├── test_llm_client.py
    ├── test_data_packer.py
    ├── test_audit_logger.py
    ├── test_mate_base.py
    ├── test_orchestrator.py
    ├── test_decisions_store.py
    ├── test_experience_store.py
    ├── test_binance_client.py
    └── integration/
        ├── test_full_mode_dry_run.py
        ├── test_lean_mode_dry_run.py
        └── test_tracking_mode_dry_run.py
```

**复用旧文件**（位于项目根 `D:/workspace/pythonProject/0515/`，agent_system 通过相对路径或 sys.path 引用）：
- `funding_rate.py`：旧公开接口，binance_client.py 在签名版上覆盖一份
- `db.py`：原表结构保留，agent_system/data/db.py 引用并扩展
- `fetch_funding_data.py` / `fetch_kline_data.py` / `fetch_position_data.py`：采集脚本，不改造
- `coin_groups.py`：scan_runner 用其分组
- `signals.py`：scan_runner 调用作"预筛子"
- `funding_rate.db`：复用，新表叠加

---

## Phase 1 — 基础设施与单 Mate 跑通

**目标**：CLI 跑通"输入 ETHUSDT → DataPack → 1 个 Mate(trend_multi_tf) → 输出合法 JSON"。

### Task 1.1: 项目脚手架 + requirements

**Files:**
- Create: `agent_system/__init__.py`
- Create: `agent_system/requirements.txt`
- Create: `agent_system/core/__init__.py`
- Create: `agent_system/providers/__init__.py`
- Create: `agent_system/mates/__init__.py`
- Create: `agent_system/runners/__init__.py`
- Create: `agent_system/data/__init__.py`
- Create: `agent_system/web/__init__.py`
- Create: `agent_system/push/__init__.py`
- Create: `agent_system/cli/__init__.py`
- Create: `agent_system/tests/__init__.py`
- Create: `agent_system/tests/integration/__init__.py`

- [ ] **Step 1: 创建所有 `__init__.py` 空文件（让 Python 识别为 package）**

每个 `__init__.py` 都是空文件，仅提供包标识。

- [ ] **Step 2: 创建 `agent_system/requirements.txt`**

```
flask>=2.3.0
requests>=2.31.0
pyyaml>=6.0
pytest>=7.4.0
pytest-mock>=3.11.0
```

- [ ] **Step 3: 验证目录结构**

Run: `python -c "import agent_system; print('ok')"`（在 `D:/workspace/pythonProject/0515/` 下执行）
Expected: 输出 `ok`

- [ ] **Step 4: 安装依赖**

Run: `pip install -r agent_system/requirements.txt`
Expected: 全部安装成功

- [ ] **Step 5: Commit**

```bash
git add agent_system/
git commit -m "feat: agent_system 项目脚手架"
```

---

### Task 1.2: config_loader 加载 YAML 并解引用环境变量

**Files:**
- Create: `agent_system/config.yaml`
- Create: `agent_system/core/config_loader.py`
- Test: `agent_system/tests/test_config_loader.py`

- [ ] **Step 1: 创建 `config.yaml` 最小可用版本**

```yaml
default_model: deepseek-chat
audit_dir: tracks/
data_db: funding_rate.db

providers:
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com
    models: [deepseek-chat, deepseek-reasoner]

binance:
  api_key_env: BINANCE_API_KEY
  api_secret_env: BINANCE_API_SECRET
  use_signed_for_quota: true

mates:
  trend_multi_tf:
    model: deepseek-chat
    temperature: 0.2
    max_tokens: 1500
    enabled: true
    prompt_file: prompts/trend_multi_tf.md

modes:
  full:
    enabled_mates: [trend_multi_tf]
    rounds: 3

scheduler:
  scan_interval_min: 30
  tracking_interval_min: 15
  retrospective_cron: "0 3 * * *"
  scan_max_candidates: 10
  scan_min_score: 30

push:
  server_chan:
    enabled: false
    key_env: SERVER_CHAN_KEY
  cooldown_min: 240

defaults:
  temperature: 0.3
  max_tokens: 2000
  timeout_sec: 30
  retry_max: 2
```

- [ ] **Step 2: 写失败的测试 `test_config_loader.py`**

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest agent_system/tests/test_config_loader.py -v`
Expected: FAIL "ModuleNotFoundError: No module named 'agent_system.core.config_loader'"

- [ ] **Step 4: 实现 `core/config_loader.py`**

```python
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest agent_system/tests/test_config_loader.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent_system/config.yaml agent_system/core/config_loader.py agent_system/tests/test_config_loader.py
git commit -m "feat: config_loader 加载 YAML 与环境变量解引用"
```

---

### Task 1.3: audit_logger 写 JSON 审计

**Files:**
- Create: `agent_system/core/audit_logger.py`
- Test: `agent_system/tests/test_audit_logger.py`

- [ ] **Step 1: 写失败的测试**

```python
import json
import os
from agent_system.core.audit_logger import AuditLogger

def test_audit_log_call_creates_file(tmp_path):
    logger = AuditLogger(audit_dir=str(tmp_path))
    audit_id = logger.start_session(prefix="decision", session_key="42")
    logger.log_call(
        audit_id=audit_id,
        round_num=1,
        mate="trend_multi_tf",
        model="deepseek-chat",
        prompt="test prompt",
        response="test response",
        tokens={"prompt": 10, "completion": 20, "total": 30},
        duration_ms=1000,
    )
    logger.finalize(audit_id, final_card={"direction": "多"})

    files = list(tmp_path.glob("decision_42.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["session_key"] == "42"
    assert len(data["rounds"][0]["calls"]) == 1
    assert data["final_card"]["direction"] == "多"

def test_log_call_groups_by_round(tmp_path):
    logger = AuditLogger(audit_dir=str(tmp_path))
    aid = logger.start_session(prefix="decision", session_key="1")
    logger.log_call(aid, 1, "m1", "deepseek-chat", "p", "r", {"total": 1}, 100)
    logger.log_call(aid, 1, "m2", "deepseek-chat", "p", "r", {"total": 1}, 100)
    logger.log_call(aid, 2, "m3", "deepseek-chat", "p", "r", {"total": 1}, 100)
    logger.finalize(aid, final_card={})
    data = json.loads((tmp_path / "decision_1.json").read_text(encoding="utf-8"))
    assert len(data["rounds"]) == 2
    assert len(data["rounds"][0]["calls"]) == 2
    assert len(data["rounds"][1]["calls"]) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_audit_logger.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `core/audit_logger.py`**

```python
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

class AuditLogger:
    def __init__(self, audit_dir: str):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._sessions = {}

    def start_session(self, prefix: str, session_key: str) -> str:
        audit_id = str(uuid.uuid4())
        self._sessions[audit_id] = {
            "prefix": prefix,
            "session_key": session_key,
            "started_at": datetime.now().isoformat(),
            "rounds": {},
            "final_card": None,
        }
        return audit_id

    def log_call(self, audit_id, round_num, mate, model, prompt, response, tokens, duration_ms):
        session = self._sessions[audit_id]
        rounds = session["rounds"]
        if round_num not in rounds:
            rounds[round_num] = []
        rounds[round_num].append({
            "mate": mate,
            "model": model,
            "prompt": prompt,
            "response": response,
            "tokens": tokens,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
        })

    def finalize(self, audit_id, final_card):
        session = self._sessions.pop(audit_id)
        session["final_card"] = final_card
        rounds_list = [
            {"round": k, "calls": session["rounds"][k]}
            for k in sorted(session["rounds"].keys())
        ]
        out = {
            "session_key": session["session_key"],
            "started_at": session["started_at"],
            "finalized_at": datetime.now().isoformat(),
            "rounds": rounds_list,
            "final_card": final_card,
        }
        path = self.audit_dir / f"{session['prefix']}_{session['session_key']}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_audit_logger.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/core/audit_logger.py agent_system/tests/test_audit_logger.py
git commit -m "feat: audit_logger 落盘多轮 LLM 审计 JSON"
```

---

### Task 1.4: providers/deepseek 实现

**Files:**
- Create: `agent_system/providers/base.py`
- Create: `agent_system/providers/deepseek.py`
- Create: `agent_system/providers/claude.py`
- Create: `agent_system/providers/openai.py`

- [ ] **Step 1: 实现 `providers/base.py` 抽象基类**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMResponse:
    text: str
    usage: dict
    model: str
    raw: dict

class BaseProvider:
    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        response_format: Optional[str],
        timeout: int,
    ) -> LLMResponse:
        raise NotImplementedError
```

- [ ] **Step 2: 实现 `providers/deepseek.py`**

```python
import requests
from .base import BaseProvider, LLMResponse

class DeepSeekProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def chat(self, model, messages, temperature, max_tokens, response_format, timeout):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            usage={
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0),
            },
            model=model,
            raw=data,
        )
```

- [ ] **Step 3: 实现 `providers/claude.py` 和 `providers/openai.py` 桩**

`providers/claude.py`:
```python
from .base import BaseProvider

class ClaudeProvider(BaseProvider):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("Claude provider 第一阶段不接")
```

`providers/openai.py`:
```python
from .base import BaseProvider

class OpenAIProvider(BaseProvider):
    def __init__(self, *args, **kwargs):
        raise NotImplementedError("OpenAI provider 第一阶段不接")
```

- [ ] **Step 4: Commit**

```bash
git add agent_system/providers/
git commit -m "feat: LLM provider 抽象 + DeepSeek 实现 + Claude/OpenAI 桩"
```

---

### Task 1.5: llm_client 按 model 前缀分发

**Files:**
- Create: `agent_system/core/llm_client.py`
- Test: `agent_system/tests/test_llm_client.py`

- [ ] **Step 1: 写失败的测试**

```python
import pytest
from unittest.mock import MagicMock
from agent_system.core.llm_client import LLMClient
from agent_system.providers.base import LLMResponse

def test_dispatch_to_deepseek():
    cfg = {
        "providers": {
            "deepseek": {"api_key_env": "DEEPSEEK_API_KEY"},
        },
        "defaults": {"timeout_sec": 30, "retry_max": 2},
    }
    mock_provider = MagicMock()
    mock_provider.chat.return_value = LLMResponse(
        text="hi", usage={"total_tokens": 5}, model="deepseek-chat", raw={}
    )
    client = LLMClient(cfg, providers={"deepseek": mock_provider})
    resp = client.chat(model="deepseek-chat", messages=[{"role": "user", "content": "hi"}])
    assert resp.text == "hi"
    mock_provider.chat.assert_called_once()

def test_unknown_model_raises():
    cfg = {"providers": {}, "defaults": {}}
    client = LLMClient(cfg, providers={})
    with pytest.raises(ValueError):
        client.chat(model="unknown-xyz", messages=[])

def test_retry_on_exception():
    cfg = {"providers": {"deepseek": {}}, "defaults": {"retry_max": 2, "timeout_sec": 30}}
    mock_provider = MagicMock()
    mock_provider.chat.side_effect = [
        Exception("boom"),
        LLMResponse(text="ok", usage={"total_tokens": 1}, model="deepseek-chat", raw={}),
    ]
    client = LLMClient(cfg, providers={"deepseek": mock_provider})
    resp = client.chat(model="deepseek-chat", messages=[])
    assert resp.text == "ok"
    assert mock_provider.chat.call_count == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_llm_client.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `core/llm_client.py`**

```python
import time
from typing import Optional
from agent_system.providers.base import LLMResponse, BaseProvider

class LLMClient:
    PREFIX_MAP = {
        "deepseek-": "deepseek",
        "claude-": "claude",
        "gpt-": "openai",
    }

    def __init__(self, cfg: dict, providers: dict[str, BaseProvider]):
        self.cfg = cfg
        self.providers = providers

    def _provider_name_for_model(self, model: str) -> str:
        for prefix, name in self.PREFIX_MAP.items():
            if model.startswith(prefix):
                return name
        raise ValueError(f"No provider matches model '{model}'")

    def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = None,
        max_tokens: int = None,
        response_format: Optional[str] = None,
        timeout: int = None,
    ) -> LLMResponse:
        defaults = self.cfg.get("defaults", {})
        if temperature is None:
            temperature = defaults.get("temperature", 0.3)
        if max_tokens is None:
            max_tokens = defaults.get("max_tokens", 2000)
        if timeout is None:
            timeout = defaults.get("timeout_sec", 30)
        retry_max = defaults.get("retry_max", 2)

        provider_name = self._provider_name_for_model(model)
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Provider '{provider_name}' not initialized")

        last_err = None
        for attempt in range(retry_max + 1):
            try:
                return provider.chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout=timeout,
                )
            except Exception as e:
                last_err = e
                if attempt < retry_max:
                    time.sleep(2 ** attempt)
        raise last_err
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_llm_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/core/llm_client.py agent_system/tests/test_llm_client.py
git commit -m "feat: llm_client 按 model 前缀分发 + 指数退避重试"
```

---

### Task 1.6: data/db.py 复用旧表 + 新增 3 张表

**Files:**
- Create: `agent_system/data/db.py`
- Test: `agent_system/tests/test_db_init.py`

- [ ] **Step 1: 写失败的测试**

```python
import sqlite3
from agent_system.data.db import get_conn, init_new_tables

def test_init_creates_decisions_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='decisions'")
    assert cur.fetchone() is not None

def test_init_creates_experiences_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='experiences'")
    assert cur.fetchone() is not None

def test_init_creates_chat_messages_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'")
    assert cur.fetchone() is not None

def test_init_creates_tracked_positions_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_positions'")
    assert cur.fetchone() is not None

def test_init_creates_track_history_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    conn = get_conn(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='track_history'")
    assert cur.fetchone() is not None

def test_init_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_new_tables(db_path)
    init_new_tables(db_path)  # 不应报错
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_db_init.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `data/db.py`**

```python
import sqlite3

def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

DDL_DECISIONS = """
CREATE TABLE IF NOT EXISTS decisions (
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  trigger_mode TEXT,
  direction TEXT,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  confidence INTEGER,
  tags TEXT,
  card_json TEXT,
  audit_path TEXT,
  status TEXT,
  closed_at TEXT,
  realized_pnl_pct REAL,
  created_at TEXT
)
"""
DDL_DECISIONS_IDX_SYMBOL = "CREATE INDEX IF NOT EXISTS idx_dec_symbol ON decisions(symbol)"
DDL_DECISIONS_IDX_STATUS = "CREATE INDEX IF NOT EXISTS idx_dec_status ON decisions(status)"

DDL_EXPERIENCES = """
CREATE TABLE IF NOT EXISTS experiences (
  experience_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tags TEXT,
  scenario_summary TEXT,
  decisions_referenced TEXT,
  outcome_stats TEXT,
  lesson TEXT,
  applicable_when TEXT,
  caveats TEXT,
  created_at TEXT,
  updated_at TEXT
)
"""
DDL_EXPERIENCES_IDX = "CREATE INDEX IF NOT EXISTS idx_exp_updated ON experiences(updated_at)"

DDL_CHAT_MESSAGES = """
CREATE TABLE IF NOT EXISTS chat_messages (
  msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  role TEXT,
  content TEXT,
  decision_id INTEGER,
  created_at TEXT
)
"""
DDL_CHAT_IDX = "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id)"

DDL_TRACKED_POSITIONS = """
CREATE TABLE IF NOT EXISTS tracked_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  direction TEXT,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  status TEXT,
  created_at TEXT,
  closed_at TEXT,
  close_reason TEXT,
  notes TEXT,
  entry_signals TEXT
)
"""
DDL_TRACKED_IDX = "CREATE INDEX IF NOT EXISTS idx_track_status ON tracked_positions(status)"

DDL_TRACK_HISTORY = """
CREATE TABLE IF NOT EXISTS track_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  track_id INTEGER,
  snapshot_json TEXT,
  created_at TEXT
)
"""
DDL_TRACK_HISTORY_IDX = "CREATE INDEX IF NOT EXISTS idx_th_track ON track_history(track_id)"

def init_new_tables(db_path: str):
    conn = get_conn(db_path)
    try:
        conn.execute(DDL_DECISIONS)
        conn.execute(DDL_DECISIONS_IDX_SYMBOL)
        conn.execute(DDL_DECISIONS_IDX_STATUS)
        conn.execute(DDL_EXPERIENCES)
        conn.execute(DDL_EXPERIENCES_IDX)
        conn.execute(DDL_CHAT_MESSAGES)
        conn.execute(DDL_CHAT_IDX)
        conn.execute(DDL_TRACKED_POSITIONS)
        conn.execute(DDL_TRACKED_IDX)
        conn.execute(DDL_TRACK_HISTORY)
        conn.execute(DDL_TRACK_HISTORY_IDX)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_db_init.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/data/db.py agent_system/tests/test_db_init.py
git commit -m "feat: 数据库初始化 decisions/experiences/chat_messages 三张新表"
```

---

### Task 1.7: data/binance_client 签名版客户端

**Files:**
- Create: `agent_system/data/binance_client.py`
- Test: `agent_system/tests/test_binance_client.py`

- [ ] **Step 1: 写失败的测试（签名生成 + 公开接口请求结构）**

```python
from agent_system.data.binance_client import BinanceClient, build_signature

def test_build_signature_deterministic():
    sig1 = build_signature(secret="abc", query_string="symbol=BTCUSDT&timestamp=1")
    sig2 = build_signature(secret="abc", query_string="symbol=BTCUSDT&timestamp=1")
    assert sig1 == sig2
    assert len(sig1) == 64  # HMAC-SHA256 hex

def test_get_klines_builds_url(monkeypatch):
    captured = {}
    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        class R:
            def raise_for_status(self): pass
            def json(self): return [[1, "1", "2", "3", "4", "5", 6, "7", 8, "9", "10", "11"]]
        return R()
    import agent_system.data.binance_client as bc
    monkeypatch.setattr(bc.requests, "get", fake_get)

    client = BinanceClient(api_key="k", api_secret="s")
    out = client.get_klines("BTCUSDT", interval="1h", limit=10)
    assert "/fapi/v1/klines" in captured["url"]
    assert captured["params"]["symbol"] == "BTCUSDT"
    assert captured["params"]["interval"] == "1h"
    assert captured["params"]["limit"] == 10
    assert len(out) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_binance_client.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `data/binance_client.py`**

```python
import hashlib
import hmac
import time
import requests

def build_signature(secret: str, query_string: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

class BinanceClient:
    BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def _headers(self):
        h = {}
        if self.api_key:
            h["X-MBX-APIKEY"] = self.api_key
        return h

    def get_klines(self, symbol: str, interval: str, limit: int = 500, start_time: int = None, end_time: int = None):
        url = f"{self.BASE_URL}/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_funding_rate_history(self, symbol: str, limit: int = 1000, start_time: int = None, end_time: int = None):
        url = f"{self.BASE_URL}/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_funding_info(self):
        url = f"{self.BASE_URL}/fapi/v1/fundingInfo"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_open_interest_hist(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/openInterestHist"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_top_long_short_position_ratio(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/topLongShortPositionRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_top_long_short_account_ratio(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/topLongShortAccountRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_global_long_short_account_ratio(self, symbol: str, period: str = "1h", limit: int = 500):
        url = f"{self.BASE_URL}/futures/data/globalLongShortAccountRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_premium_index(self, symbol: str = None):
        url = f"{self.BASE_URL}/fapi/v1/premiumIndex"
        params = {"symbol": symbol} if symbol else {}
        r = requests.get(url, params=params, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_binance_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/data/binance_client.py agent_system/tests/test_binance_client.py
git commit -m "feat: 币安客户端封装(签名版,仅提高限额,不下单)"
```

---

### Task 1.8: core/data_packer 聚合 DataPack

**Files:**
- Create: `agent_system/core/data_packer.py`
- Test: `agent_system/tests/test_data_packer.py`

- [ ] **Step 1: 写失败的测试**

```python
from unittest.mock import MagicMock
from agent_system.core.data_packer import build, calc_atr, calc_bb_width

def test_calc_atr_basic():
    # 简单 K 线: [open, high, low, close, vol]
    klines = [
        {"high": 110, "low": 100, "close": 105},
        {"high": 112, "low": 103, "close": 108},
        {"high": 115, "low": 105, "close": 110},
    ]
    atr = calc_atr(klines, period=2)
    assert atr > 0

def test_calc_bb_width_basic():
    closes = [100, 101, 99, 100, 102, 98, 100, 101, 99, 100,
              102, 98, 100, 101, 99, 100, 102, 98, 100, 101]
    width = calc_bb_width(closes, period=20, std_mult=2)
    assert width > 0

def test_build_returns_required_fields(monkeypatch):
    from agent_system.core import data_packer

    class FakeBinance:
        def get_klines(self, symbol, interval, limit, **kw):
            # 返回 binance 原始格式 [openTime, o, h, l, c, v, closeTime, qv, n, tbb, tbq, _]
            return [[i*1000, "100", "110", "95", "105", "1000", i*1000+1, "100000", 10, "500", "50000", "0"]
                    for i in range(200)]
        def get_funding_rate_history(self, symbol, limit, **kw):
            return [{"symbol": symbol, "fundingRate": "0.0001", "fundingTime": 1}]
        def get_funding_info(self):
            return [{"symbol": "ETHUSDT", "adjustedFundingRateCap": "0.02",
                     "adjustedFundingRateFloor": "-0.02", "fundingIntervalHours": 8}]
        def get_open_interest_hist(self, symbol, period, limit):
            return [{"symbol": symbol, "sumOpenInterest": "100", "sumOpenInterestValue": "1000", "timestamp": 1}]
        def get_top_long_short_position_ratio(self, symbol, period, limit):
            return [{"symbol": symbol, "longShortRatio": "1.5", "timestamp": 1}]
        def get_top_long_short_account_ratio(self, symbol, period, limit):
            return [{"symbol": symbol, "longShortRatio": "1.2", "timestamp": 1}]
        def get_global_long_short_account_ratio(self, symbol, period, limit):
            return [{"symbol": symbol, "longShortRatio": "0.9", "timestamp": 1}]

    pack = build(symbol="ETHUSDT", binance=FakeBinance(), peer_symbols=["BTCUSDT"])
    assert pack["symbol"] == "ETHUSDT"
    assert "klines" in pack
    assert "1h" in pack["klines"]
    assert "4h" in pack["klines"]
    assert "1d" in pack["klines"]
    assert "1w" in pack["klines"]
    assert "funding" in pack
    assert "positions" in pack
    assert "indicators" in pack
    assert "atr_12h" in pack["indicators"]
    assert "tags" in pack
    assert isinstance(pack["tags"], list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_data_packer.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `core/data_packer.py`**

```python
import statistics
from datetime import datetime, timezone

def _parse_kline(raw):
    return {
        "open_time": raw[0],
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": raw[6],
        "quote_volume": float(raw[7]),
        "trades": raw[8],
        "taker_buy_volume": float(raw[9]),
        "taker_buy_quote_volume": float(raw[10]),
    }

def calc_atr(klines: list[dict], period: int = 12) -> float:
    if len(klines) < 2:
        return 0.0
    trs = []
    for i in range(1, len(klines)):
        h = klines[i]["high"]
        l = klines[i]["low"]
        prev_c = klines[i-1]["close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    use = trs[-period:] if len(trs) > period else trs
    return sum(use) / len(use) if use else 0.0

def calc_bb_width(closes: list[float], period: int = 20, std_mult: float = 2.0) -> float:
    if len(closes) < period:
        return 0.0
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((c - mean) ** 2 for c in window) / period
    std = variance ** 0.5
    upper = mean + std_mult * std
    lower = mean - std_mult * std
    return (upper - lower) / mean if mean else 0.0

def calc_ema(closes: list[float], period: int) -> float:
    if not closes:
        return 0.0
    k = 2 / (period + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return ema

def _bb_width_pct_rank(closes: list[float], period: int, lookback: int = 100) -> float:
    """当前 BB 带宽在过去 lookback 根中的分位 (0-100)"""
    if len(closes) < period + lookback:
        return 50.0
    widths = []
    for i in range(lookback):
        end = len(closes) - i
        widths.append(calc_bb_width(closes[:end], period))
    current = widths[0]
    rank = sum(1 for w in widths if w <= current)
    return 100.0 * rank / len(widths)

def _extract_tags(pack: dict) -> list[str]:
    tags = []
    funding_now = pack["funding"]["current"]
    if funding_now > 0.0010:
        tags.append("funding=extreme_high")
    elif funding_now < -0.0010:
        tags.append("funding=extreme_low")
    else:
        tags.append("funding=normal")

    top_pos = pack["positions"]["top_position_ratio_now"]
    if top_pos > 2.5:
        tags.append("smart_money=extreme_long")
    elif top_pos < 0.4:
        tags.append("smart_money=extreme_short")
    else:
        tags.append("smart_money=normal")

    bb_pct = pack["indicators"]["bb_width_pct"]
    if bb_pct < 25:
        tags.append("volatility=compressed")
    elif bb_pct > 75:
        tags.append("volatility=expanding")
    else:
        tags.append("volatility=normal")
    return tags

def build(symbol: str, binance, peer_symbols: list[str] = None) -> dict:
    klines_raw = {
        "1h": binance.get_klines(symbol, interval="1h", limit=168),
        "4h": binance.get_klines(symbol, interval="4h", limit=180),
        "1d": binance.get_klines(symbol, interval="1d", limit=180),
        "1w": binance.get_klines(symbol, interval="1w", limit=104),
    }
    klines = {tf: [_parse_kline(r) for r in raw] for tf, raw in klines_raw.items()}

    funding_history = binance.get_funding_rate_history(symbol, limit=90)
    funding_info_all = binance.get_funding_info()
    finfo = next((f for f in funding_info_all if f.get("symbol") == symbol), {})
    funding_now = float(funding_history[-1]["fundingRate"]) if funding_history else 0.0

    oi = binance.get_open_interest_hist(symbol, period="1h", limit=180)
    top_pos = binance.get_top_long_short_position_ratio(symbol, period="1h", limit=180)
    top_acc = binance.get_top_long_short_account_ratio(symbol, period="1h", limit=180)
    global_acc = binance.get_global_long_short_account_ratio(symbol, period="1h", limit=180)

    klines_1h = klines["1h"]
    closes_1h = [k["close"] for k in klines_1h]
    closes_1d = [k["close"] for k in klines["1d"]]

    indicators = {
        "atr_12h": calc_atr(klines_1h[-12:], period=12),
        "atr_7d": calc_atr(klines["1d"][-7:], period=7),
        "bb_width_now": calc_bb_width(closes_1h, period=20),
        "bb_width_pct": _bb_width_pct_rank(closes_1h, period=20, lookback=100),
        "ema_20_1h": calc_ema(closes_1h, 20),
        "ema_50_1h": calc_ema(closes_1h, 50),
        "ema_200_1h": calc_ema(closes_1h, 200),
        "ema_20_1d": calc_ema(closes_1d, 20),
        "ema_50_1d": calc_ema(closes_1d, 50),
        "ema_200_1d": calc_ema(closes_1d, 200),
    }

    peer_funding = {}
    if peer_symbols:
        for ps in peer_symbols:
            try:
                pf = binance.get_premium_index(ps)
                peer_funding[ps] = float(pf.get("lastFundingRate", 0))
            except Exception:
                peer_funding[ps] = None

    pack = {
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "price_now": closes_1h[-1] if closes_1h else 0.0,
        "klines": klines,
        "funding": {
            "current": funding_now,
            "history_30d": funding_history[-90:] if funding_history else [],
            "cap": float(finfo.get("adjustedFundingRateCap", 0.02)) if finfo else 0.02,
            "floor": float(finfo.get("adjustedFundingRateFloor", -0.02)) if finfo else -0.02,
            "interval_hours": int(finfo.get("fundingIntervalHours", 8)) if finfo else 8,
        },
        "positions": {
            "oi_history": oi,
            "top_position_ratio_history": top_pos,
            "top_account_ratio_history": top_acc,
            "global_account_ratio_history": global_acc,
            "top_position_ratio_now": float(top_pos[-1]["longShortRatio"]) if top_pos else 1.0,
            "top_account_ratio_now": float(top_acc[-1]["longShortRatio"]) if top_acc else 1.0,
            "global_account_ratio_now": float(global_acc[-1]["longShortRatio"]) if global_acc else 1.0,
        },
        "volume": {
            "recent_24h": sum(k["quote_volume"] for k in klines_1h[-24:]),
            "ma_7d": sum(k["quote_volume"] for k in klines_1h[-168:]) / 7,
            "taker_buy_ratio_recent": (
                sum(k["taker_buy_quote_volume"] for k in klines_1h[-24:]) /
                sum(k["quote_volume"] for k in klines_1h[-24:])
                if klines_1h and sum(k["quote_volume"] for k in klines_1h[-24:]) > 0 else 0.5
            ),
        },
        "indicators": indicators,
        "peer_funding": peer_funding,
    }
    pack["tags"] = _extract_tags(pack)
    return pack
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_data_packer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/core/data_packer.py agent_system/tests/test_data_packer.py
git commit -m "feat: data_packer 聚合 K线/费率/持仓/指标 + 标签提取"
```

---

### Task 1.9: prompts/_shared 通用模板

**Files:**
- Create: `agent_system/prompts/_shared/output_schema.md`
- Create: `agent_system/prompts/_shared/data_pack_format.md`
- Create: `agent_system/prompts/_shared/role_persona.md`

- [ ] **Step 1: `_shared/output_schema.md`**

```markdown
所有分析师的输出必须是合法 JSON,严格遵循以下 schema:

```json
{
  "mate": "<mate_name>",
  "view": "<多 | 空 | 观望>",
  "confidence": <0-100 整数>,
  "evidence": [
    "<具体数据支撑 1>",
    "<具体数据支撑 2>",
    "<具体数据支撑 3>"
  ],
  "concerns": [
    "<不利因素或不确定性 1>",
    "<不利因素或不确定性 2>"
  ],
  "extra": { ... }
}
```

字段说明:
- view: 仅取值 "多" / "空" / "观望" 三选一
- confidence: 0-100 整数,表示对该判断的置信度
- evidence: 至少 2 条,每条须含具体数据(数值/比例/时段)
- concerns: 0-3 条,自我标注的不确定因素
- extra: Mate 各自补充字段,详见各 Mate 的特定要求

输出时不要包含任何 JSON 之外的文字。不要使用 Markdown 包围。
```

- [ ] **Step 2: `_shared/data_pack_format.md`**

```markdown
你将收到一份 DataPack JSON,包含以下字段:

- symbol: 交易对
- timestamp: 数据生成时间(ISO 8601)
- price_now: 当前价(USDT)
- klines: 多周期 K 线 {1h, 4h, 1d, 1w},每根含 open/high/low/close/volume/quote_volume/taker_buy_volume/taker_buy_quote_volume
- funding: 资金费率 {current, history_30d, cap, floor, interval_hours}
- positions:
  - oi_history: 持仓量历史
  - top_position_ratio_history / top_position_ratio_now: 大户持仓多空比
  - top_account_ratio_history / top_account_ratio_now: 大户账户多空比
  - global_account_ratio_history / global_account_ratio_now: 全市场多空比
- volume: {recent_24h, ma_7d, taker_buy_ratio_recent}
- indicators: {atr_12h, atr_7d, bb_width_now, bb_width_pct, ema_*}
- peer_funding: 跨币种当前费率 {BTCUSDT: ..., ...}
- tags: 自动提取的场景标签

只引用与你职责相关的字段。
```

- [ ] **Step 3: `_shared/role_persona.md`**

```markdown
你是币安 U 本位永续合约的专业分析师。

**原则:**
- 只用数据说话,不臆测
- 引用具体数值(价格/比率/百分比/根数)
- 不重复其他分析师的工作,聚焦自己的维度
- 如果数据不足以判断,直接给 view="观望" + 低 confidence,不要硬分析
- 输出严格 JSON,不要 Markdown,不要解释,不要中括号围绕的注释
```

- [ ] **Step 4: Commit**

```bash
git add agent_system/prompts/_shared/
git commit -m "feat: _shared prompt 通用模板(output_schema/data_pack/role_persona)"
```

---

### Task 1.10: mates/base.py — Mate 基类

**Files:**
- Create: `agent_system/mates/base.py`
- Test: `agent_system/tests/test_mate_base.py`

- [ ] **Step 1: 写失败的测试**

```python
import json
from unittest.mock import MagicMock
from agent_system.mates.base import BaseMate
from agent_system.providers.base import LLMResponse

def test_render_prompt_replaces_placeholders(tmp_path):
    prompts_dir = tmp_path / "prompts"
    shared = prompts_dir / "_shared"
    shared.mkdir(parents=True)
    (shared / "output_schema.md").write_text("SCHEMA")
    (shared / "data_pack_format.md").write_text("DATAFMT")
    (shared / "role_persona.md").write_text("PERSONA")
    (prompts_dir / "test_mate.md").write_text(
        "{{ role_persona }}\n{{ data_pack_format }}\n{{ output_schema }}\n{{ data_pack_json }}\n"
    )

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{"view":"多","confidence":50,"evidence":["e"]}',
                               usage={"total_tokens": 1}, model="deepseek-chat", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "temperature": 0.2, "max_tokens": 1000, "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    rendered = mate.render_prompt({"symbol": "ETH", "tags": []})
    assert "PERSONA" in rendered
    assert "DATAFMT" in rendered
    assert "SCHEMA" in rendered
    assert '"symbol": "ETH"' in rendered

def test_run_returns_parsed_json(tmp_path):
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("{{ data_pack_json }}")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text='{"view":"多","confidence":75,"evidence":["a"]}',
                               usage={"total_tokens": 1}, model="deepseek-chat", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "temperature": 0.2, "max_tokens": 1000, "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    result = mate.run({"symbol": "ETH"})
    assert result["view"] == "多"
    assert result["confidence"] == 75
    assert result["mate"] == "test_mate"

def test_run_handles_invalid_json(tmp_path):
    prompts_dir = tmp_path / "prompts"
    (prompts_dir / "_shared").mkdir(parents=True)
    (prompts_dir / "_shared" / "output_schema.md").write_text("S")
    (prompts_dir / "_shared" / "data_pack_format.md").write_text("D")
    (prompts_dir / "_shared" / "role_persona.md").write_text("R")
    (prompts_dir / "test_mate.md").write_text("X")

    class MockLLM:
        def chat(self, **kw):
            return LLMResponse(text="not json", usage={}, model="deepseek-chat", raw={})

    mate = BaseMate(
        name="test_mate",
        llm_client=MockLLM(),
        mate_cfg={"model": "deepseek-chat", "prompt_file": "prompts/test_mate.md"},
        prompts_dir=str(prompts_dir),
    )
    result = mate.run({"symbol": "ETH"})
    assert result["view"] == "观望"
    assert result["confidence"] == 0
    assert "_error" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_mate_base.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `mates/base.py`**

```python
import json
import re
import time
from pathlib import Path

class BaseMate:
    def __init__(self, name, llm_client, mate_cfg, prompts_dir):
        self.name = name
        self.llm = llm_client
        self.cfg = mate_cfg
        self.prompts_dir = Path(prompts_dir)
        self._template = None
        self._shared = None

    def _load(self):
        if self._template is None:
            prompt_file = self.cfg["prompt_file"]
            full_path = self.prompts_dir.parent / prompt_file if not str(prompt_file).startswith(str(self.prompts_dir)) else Path(prompt_file)
            if not full_path.exists():
                full_path = self.prompts_dir / Path(prompt_file).name
            self._template = full_path.read_text(encoding="utf-8")
            shared_dir = self.prompts_dir / "_shared"
            self._shared = {
                "role_persona": (shared_dir / "role_persona.md").read_text(encoding="utf-8"),
                "data_pack_format": (shared_dir / "data_pack_format.md").read_text(encoding="utf-8"),
                "output_schema": (shared_dir / "output_schema.md").read_text(encoding="utf-8"),
            }

    def render_prompt(self, data_pack: dict, extra_ctx: dict = None) -> str:
        self._load()
        rendered = self._template
        for k, v in self._shared.items():
            rendered = rendered.replace("{{ " + k + " }}", v)
        rendered = rendered.replace("{{ data_pack_json }}", json.dumps(data_pack, ensure_ascii=False, default=str))
        if extra_ctx:
            for k, v in extra_ctx.items():
                rendered = rendered.replace("{{ " + k + " }}", json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v)
        return rendered

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)

    def run(self, data_pack: dict, extra_ctx: dict = None, audit_logger=None, audit_id=None, round_num=1) -> dict:
        prompt = ""
        try:
            prompt = self.render_prompt(data_pack, extra_ctx)
        except Exception as e:
            return {"mate": self.name, "view": "观望", "confidence": 0,
                    "evidence": [], "_error": f"render failed: {e}"}
        messages = [{"role": "user", "content": prompt}]
        start = time.time()
        try:
            resp = self.llm.chat(
                model=self.cfg["model"],
                messages=messages,
                temperature=self.cfg.get("temperature"),
                max_tokens=self.cfg.get("max_tokens"),
                response_format="json",
            )
            duration_ms = int((time.time() - start) * 1000)
            try:
                parsed = self._parse_json(resp.text)
            except Exception as e:
                parsed = {"view": "观望", "confidence": 0, "evidence": [],
                          "_error": f"JSON parse failed: {e}", "_raw": resp.text[:500]}
            parsed["mate"] = self.name
            if audit_logger and audit_id:
                audit_logger.log_call(
                    audit_id=audit_id, round_num=round_num, mate=self.name,
                    model=self.cfg["model"], prompt=prompt, response=resp.text,
                    tokens=resp.usage, duration_ms=duration_ms,
                )
            return parsed
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            err_result = {"mate": self.name, "view": "观望", "confidence": 0,
                          "evidence": [], "_error": f"LLM call failed: {e}"}
            if audit_logger and audit_id:
                audit_logger.log_call(
                    audit_id=audit_id, round_num=round_num, mate=self.name,
                    model=self.cfg.get("model", "?"), prompt=prompt, response=str(e),
                    tokens={}, duration_ms=duration_ms,
                )
            return err_result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_mate_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/mates/base.py agent_system/tests/test_mate_base.py
git commit -m "feat: Mate 基类(模板渲染 + JSON 解析 + 异常降级 + 审计)"
```

---

### Task 1.11: mates/trend_multi_tf 第一个具体 Mate

**Files:**
- Create: `agent_system/mates/trend_multi_tf.py`
- Create: `agent_system/prompts/trend_multi_tf.md`

- [ ] **Step 1: 写 `prompts/trend_multi_tf.md`**

```markdown
{{ role_persona }}

## 角色

你是多周期趋势分析师。专注于通过 1h/4h/1d/1w 多个周期的 K 线、均线排列、MACD 指标判断当前趋势方向。

## 输入

{{ data_pack_format }}

## 关注维度

- 1h 周期: 短期动能、近期突破/跌破、与 EMA 20/50/200 的关系
- 4h 周期: 中期方向、是否多头/空头排列
- 1d 周期: 大趋势、与 EMA 200 的距离
- 1w 周期: 长期格局
- 多周期协同: 是否一致或背离
- MACD: 通过近 N 根 close 计算近似(无需精确)

## 输出格式

{{ output_schema }}

`extra` 字段必须包含:
```json
{
  "cycle_summary": {
    "1h": "<一句话>",
    "4h": "<一句话>",
    "1d": "<一句话>",
    "1w": "<一句话>"
  },
  "alignment": "<all_bullish | all_bearish | mixed | 1h_diverge>"
}
```

## 数据

{{ data_pack_json }}
```

- [ ] **Step 2: 实现 `mates/trend_multi_tf.py`**

```python
from agent_system.mates.base import BaseMate

class TrendMultiTfMate(BaseMate):
    pass
```

注：第一阶段所有 Mate 都直接复用 BaseMate 的逻辑，差异在 prompt。后续如需特殊行为再覆写。

- [ ] **Step 3: Commit**

```bash
git add agent_system/mates/trend_multi_tf.py agent_system/prompts/trend_multi_tf.md
git commit -m "feat: trend_multi_tf 多周期趋势分析师"
```

---

### Task 1.12: cli/__main__ dry_run 命令

**Files:**
- Create: `agent_system/cli/__main__.py`

- [ ] **Step 1: 实现 `cli/__main__.py`**

```python
import argparse
import json
import os
import sys
from pathlib import Path

from agent_system.core.config_loader import load_config, get_mate_config, resolve_provider_key
from agent_system.core.llm_client import LLMClient
from agent_system.core.data_packer import build as build_pack
from agent_system.core.audit_logger import AuditLogger
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
    print(f"  → tags: {pack['tags']}")
    print(f"  → price_now: {pack['price_now']}")

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
```

- [ ] **Step 2: 端到端验证 Phase 1**

确保环境变量 `DEEPSEEK_API_KEY`、`BINANCE_API_KEY`、`BINANCE_API_SECRET` 已设置。

Run: `python -m agent_system.cli dry_run --symbol ETHUSDT --mate trend_multi_tf`
Expected:
- 输出 `[1/3] Fetching data for ETHUSDT...`
- 输出 `tags: [...]`
- 输出 `[2/3] Running mate 'trend_multi_tf'...`
- 输出 `[3/3] Result:` 后面是合法 JSON,含 `view`、`confidence`、`evidence`、`extra.cycle_summary`、`extra.alignment`

- [ ] **Step 3: Commit**

```bash
git add agent_system/cli/__main__.py
git commit -m "feat: CLI dry_run --mate 端到端跑通单 Mate"
```

---

## Phase 2 — 完整 11 Mate + 三轮辩论

**目标**：CLI 跑通 `full` 模式完整决策卡片，11 Mate 三轮辩论。

### Task 2.1: 9 个 Mate 类（除已实现的 trend）

**Files:**
- Create: `agent_system/mates/funding_rate.py`
- Create: `agent_system/mates/smart_money.py`
- Create: `agent_system/mates/long_short_compare.py`
- Create: `agent_system/mates/volatility.py`
- Create: `agent_system/mates/red_team.py`
- Create: `agent_system/mates/macro_sentiment.py`
- Create: `agent_system/mates/liquidity.py`
- Create: `agent_system/mates/position_mgr.py`
- Create: `agent_system/mates/decision_lead.py`
- Create: `agent_system/mates/experience.py` (空壳)

- [ ] **Step 1: 创建 9 个 Mate 类（全部继承 BaseMate，差异在 prompt）**

每个文件内容相同模板，把 `funding_rate` 替换为对应名字：

`mates/funding_rate.py`:
```python
from agent_system.mates.base import BaseMate

class FundingRateMate(BaseMate):
    pass
```

同样模板创建：smart_money.py（SmartMoneyMate）、long_short_compare.py（LongShortCompareMate）、volatility.py（VolatilityMate）、macro_sentiment.py（MacroSentimentMate）、liquidity.py（LiquidityMate）、position_mgr.py（PositionMgrMate）、experience.py（ExperienceMate）。

- [ ] **Step 2: 创建 `mates/red_team.py`，覆写 run 以支持反驳模式**

```python
from agent_system.mates.base import BaseMate

class RedTeamMate(BaseMate):
    def run_rebuttal(self, data_pack: dict, round_1_reports: list, majority_view: str,
                     audit_logger=None, audit_id=None):
        """第 2 轮反驳模式: 接收第 1 轮所有 Mate 输出 + 多数派观点"""
        extra = {
            "round_1_reports_json": round_1_reports,
            "majority_view": majority_view,
            "mode": "rebuttal",
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=2)
```

- [ ] **Step 3: 创建 `mates/decision_lead.py`，覆写为综合决策器**

```python
from agent_system.mates.base import BaseMate

class DecisionLeadMate(BaseMate):
    def synthesize(self, data_pack: dict, round_1_reports: list, round_2_debate: dict,
                   audit_logger=None, audit_id=None) -> dict:
        """第 3 轮: 综合所有材料,产出决策卡片 (注意输出 schema 与普通 Mate 不同)"""
        extra = {
            "round_1_reports_json": round_1_reports,
            "round_2_debate_json": round_2_debate,
        }
        return self.run(data_pack, extra_ctx=extra,
                        audit_logger=audit_logger, audit_id=audit_id, round_num=3)
```

- [ ] **Step 4: Commit**

```bash
git add agent_system/mates/
git commit -m "feat: 实现剩余 9 个 Mate 类(red_team/decision_lead 覆写专用方法)"
```

---

### Task 2.2: 9 个 Mate 的 prompt 模板

**Files:**
- Create: `agent_system/prompts/funding_rate.md`
- Create: `agent_system/prompts/smart_money.md`
- Create: `agent_system/prompts/long_short_compare.md`
- Create: `agent_system/prompts/volatility.md`
- Create: `agent_system/prompts/red_team.md`
- Create: `agent_system/prompts/macro_sentiment.md`
- Create: `agent_system/prompts/liquidity.md`
- Create: `agent_system/prompts/position_mgr.md`
- Create: `agent_system/prompts/decision_lead.md`
- Create: `agent_system/prompts/experience.md`

- [ ] **Step 1: `funding_rate.md`**

```markdown
{{ role_persona }}

## 角色
你是资金费率分析师。专注于通过费率绝对值、近期趋势、跨币种对比识别多空拥挤与潜在反转。

## 输入
{{ data_pack_format }}

## 关注维度
- 当前费率 vs cap/floor 的距离
- 近 30 天费率分布: 是否处于极端分位
- 与 BTC/SOL 等主流币费率的差异
- 费率方向变化趋势(过去 8h/24h/7d)

## 判定参考
- 费率 > 0.0010 或 < -0.0010: extreme,通常意味着拥挤,反转风险高
- 费率持续单边偏高/偏低: trending,情绪在酝酿
- 费率震荡接近 0: normal

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{ "risk_flag": "<拥挤 | 正常>" }
```

## 数据
{{ data_pack_json }}
```

- [ ] **Step 2: `smart_money.md`**

```markdown
{{ role_persona }}

## 角色
你是聪明钱分析师。通过大户持仓比、大户账户比、持仓量变化、主买主卖识别机构动向。

## 输入
{{ data_pack_format }}

## 关注维度
- top_position_ratio_now: 大户(头部)持仓多空比, > 2.5 极度看多, < 0.4 极度看空
- top_account_ratio_now: 大户账户多空比
- oi_history: 持仓量近期变化(增长率)
- volume.taker_buy_ratio_recent: 主买占比, > 0.6 多头主动 / < 0.4 空头主动
- 大户与持仓量同步上升 + 价格无大动 = 大资金悄悄建仓

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{ "smart_money_direction": "<多 | 空 | 中性>" }
```

## 数据
{{ data_pack_json }}
```

- [ ] **Step 3: `long_short_compare.md`**

```markdown
{{ role_persona }}

## 角色
你是多空对比分析师。通过比较大户多空比与全市场多空比,识别散户被收割的概率。

## 输入
{{ data_pack_format }}

## 关注维度
- top_position_ratio_now (大户持仓多空比)
- global_account_ratio_now (全市场多空比)
- 二者差值: > 0.8 强背离, 0.3-0.8 弱背离, < 0.3 一致
- 背离方向: 大户偏多但散户偏空,通常上涨概率高;反之亦然

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{ "divergence_score": <0-100> }
```

divergence_score 0=完全一致, 100=最大背离。

## 数据
{{ data_pack_json }}
```

- [ ] **Step 4: `volatility.md`**

```markdown
{{ role_persona }}

## 角色
你是波动压缩分析师。通过 ATR、布林带带宽、价格收敛形态识别突破机会。

## 输入
{{ data_pack_format }}

## 关注维度
- indicators.atr_12h vs atr_7d 比值 < 0.4: 严重压缩,弹簧蓄力
- indicators.bb_width_pct: 当前带宽在过去 100 根的分位
  - < 25 分位: 严重压缩
  - > 75 分位: 已扩张
- 1h K 线近 12-24 根的高低点是否收敛
- 压缩 + 大户多空比偏离: 突破信号增强

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{ "breakout_imminent": <true | false> }
```

注意: 单独的"压缩"不构成方向判断,只能给出 view="观望" 加 breakout_imminent=true,把方向交给其他分析师。

## 数据
{{ data_pack_json }}
```

- [ ] **Step 5: `red_team.md`**

```markdown
{{ role_persona }}

## 角色
你是蒋军(Red Team)风险分析师。你的职责不是预测涨跌,而是以对立面视角列出最可能让人亏钱的风险路径。

## 输入
{{ data_pack_format }}

## 工作模式

**第 1 轮独立判断模式**(extra.mode 不存在或为空):
- 在不看其他人的情况下,直接列出当前布局下最可能让人亏钱的 3 条主要风险路径
- 给出 counterview(对立面方向)及其触发条件

**第 2 轮反驳模式**(extra.mode == "rebuttal"):
- 你会拿到 round_1_reports_json (第 1 轮所有 Mate 的输出列表)
- 和 majority_view (多数派观点: "多" 或 "空" 或 "观望")
- 任务: 逐条反驳多数派的核心论据,指出可能被忽略的盲点
- 不要无脑唱反调,要拿数据和情景反驳
- 对 view 高 confidence 的 Mate 要重点质疑

## 输出格式

```json
{
  "mate": "red_team",
  "view": "<多 | 空 | 观望>",
  "confidence": <0-100>,
  "evidence": ["<不利证据 1>", "..."],
  "extra": {
    "counterview": "<多 | 空 | 观望>",
    "risks": [
      {"path": "<风险路径描述>", "probability": "<高/中/低>", "trigger": "<触发条件>"},
      ...
    ],
    "black_swan_scenarios": ["<黑天鹅场景 1>", ...],
    "rebuttal": "<仅 rebuttal 模式: 对多数派的具体反驳>"
  }
}
```

## 数据
{{ data_pack_json }}

## 第 1 轮报告(仅 rebuttal 模式可用)
{{ round_1_reports_json }}

## 多数派观点(仅 rebuttal 模式可用)
{{ majority_view }}
```

- [ ] **Step 6: `macro_sentiment.md`**

```markdown
{{ role_persona }}

## 角色
你是宏观情绪分析师。通过 BTC 主导率(BTC 与 ETH 的资金费率/价格联动)、相关币联动判断整体加密市场情绪。

## 输入
{{ data_pack_format }}

## 关注维度
- 当前 symbol 的费率与 BTC/SOL 等头部币种的差异
- BTC 自身的趋势状态(可参考 peer_funding 推断 BTC 拥挤度)
- 相关性: 当前币与 BTC 的同步性
- 1d/1w 周期判断市场是否处于 bull / bear / range

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{ "market_regime": "<牛 | 熊 | 震荡>" }
```

## 数据
{{ data_pack_json }}
```

- [ ] **Step 7: `liquidity.md`**

```markdown
{{ role_persona }}

## 角色
你是流动性分析师。第一阶段没有 L2 订单簿数据,你通过持仓量、成交量、主买主卖比近似判断流动性健康度。

## 输入
{{ data_pack_format }}

## 关注维度
- volume.recent_24h 和 volume.ma_7d 比较: 流动性放大/萎缩
- positions.oi_history 增长率: 持仓增加意味着资金进入
- volume.taker_buy_ratio_recent: 主买/主卖占比是否极端
- 流动性差(成交量萎缩 + 持仓量下降): 价格容易被推动,但不可靠
- 流动性好(成交量稳定 + 主买卖均衡): 趋势可信度高

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{ "liquidity_health": "<好 | 一般 | 差>" }
```

## 数据
{{ data_pack_json }}
```

- [ ] **Step 8: `position_mgr.md`**

```markdown
{{ role_persona }}

## 角色
你是仓位管理师。基于其他 Mate 的输出,计算具体的止损/止盈/仓位大小。

## 输入
{{ data_pack_format }}

你会拿到 round_1_reports_json,包含其他 Mate 的判断。

## 关注维度
- 综合其他 Mate 的方向倾向 + confidence 加权,确定主方向
- 止损: 基于 ATR(数据中的 indicators.atr_12h, atr_7d)和近期支撑/阻力
- 止盈: 风险报酬比 2:1 起步, 强信号可加大
- 仓位大小: confidence 加权 (高 confidence + 多 Mate 共识 → 大仓位; 否则保守)

## 计算逻辑
- 主方向 = 多数派(忽略 view="观望" 的)
- 止损距离 ≈ atr_12h × 1.5 (短线) 到 atr_7d × 1.2 (中线)
- 止盈距离 = 止损距离 × risk_reward_ratio (2.0~3.0)
- 仓位大小: 5% (低 confidence) 到 25% (高共识强信号)

## 输出格式

```json
{
  "mate": "position_mgr",
  "view": "<参考主方向>",
  "confidence": <反映共识度,0-100>,
  "evidence": ["<计算依据>"],
  "extra": {
    "entry_price": <数字>,
    "entry_zone": [<下限>, <上限>],
    "stop_loss": <数字>,
    "take_profit": <数字>,
    "risk_reward_ratio": <数字>,
    "position_size_pct": <0-100>
  }
}
```

## 第 1 轮其他 Mate 报告
{{ round_1_reports_json }}

## 数据
{{ data_pack_json }}
```

- [ ] **Step 9: `decision_lead.md`**

```markdown
{{ role_persona }}

## 角色
你是决策 Lead。综合所有 Mate 的第 1 轮独立分析、第 2 轮蒋军反驳与回应,产出最终决策卡片。

## 输入
{{ data_pack_format }}

## 综合规则
- 优先尊重多 Mate 共识,但若蒋军反驳有据,需折中
- confidence 是加权后的全局可信度
- evidence 选 3 条最有力的(注明 Mate 来源)
- key_risks 选 3 条最值得警惕的(主要来自蒋军)
- execution_plan 给出明确的入场策略 + 止损止盈触发条件

## 输出格式(决策卡片,与普通 Mate schema 不同)

```json
{
  "decision_id": null,
  "symbol": "<symbol>",
  "timestamp": "<ISO 时间>",
  "direction": "<多 | 空 | 观望>",
  "entry_price": <数字>,
  "entry_zone": [<下限>, <上限>],
  "stop_loss": <数字>,
  "take_profit": <数字>,
  "risk_reward_ratio": <数字>,
  "position_size_pct": <0-100>,
  "confidence": <0-100>,
  "key_evidence": [
    "<证据 1 (来源 Mate)>",
    "<证据 2 (来源 Mate)>",
    "<证据 3 (来源 Mate)>"
  ],
  "key_risks": [
    "<风险 1 (来源)>",
    "<风险 2 (来源)>",
    "<风险 3 (来源)>"
  ],
  "execution_plan": "<一段执行说明,含分批进场/止损/止盈触发条件/特殊场景应对>"
}
```

注意:
- entry_price/zone/stop_loss/take_profit/risk_reward_ratio/position_size_pct 直接采用 position_mgr 的输出
- 如果 direction == "观望",可将以上数值字段设为 null

## 第 1 轮所有 Mate 报告
{{ round_1_reports_json }}

## 第 2 轮辩论
{{ round_2_debate_json }}

## 数据
{{ data_pack_json }}
```

- [ ] **Step 10: `experience.md`** (空壳，Phase 4 实现)

```markdown
{{ role_persona }}

## 角色
你是经验复盘分析师。通过检索经验库,找出当前场景标签的历史经验,提供"上次这种场景赢了/输了"的参考。

## 输入
{{ data_pack_format }}

你会拿到 retrieved_experiences_json,包含按标签匹配检索出的历史经验列表。

## 输出
{{ output_schema }}

`extra` 必须包含:
```json
{
  "similar_cases": [
    {"tags": [...], "outcome_stats": {...}, "lesson": "..."}
  ]
}
```

如果未检索到任何经验, view="观望", confidence=0, evidence 中说明"经验库尚未有匹配场景"。

## 数据
{{ data_pack_json }}

## 检索到的历史经验
{{ retrieved_experiences_json }}
```

- [ ] **Step 11: Commit**

```bash
git add agent_system/prompts/
git commit -m "feat: 11 个 Mate 的 prompt 模板"
```

---

### Task 2.3: orchestrator 三轮辩论编排

**Files:**
- Create: `agent_system/core/orchestrator.py`
- Test: `agent_system/tests/test_orchestrator.py`

- [ ] **Step 1: 写失败的测试（用 mock Mate 验证流程）**

```python
import pytest
from unittest.mock import MagicMock
from agent_system.core.orchestrator import Orchestrator

def _mock_mate(name, view="多", confidence=70):
    m = MagicMock()
    m.name = name
    m.run.return_value = {"mate": name, "view": view, "confidence": confidence,
                          "evidence": ["e"], "extra": {}}
    return m

def test_round_1_calls_all_enabled_mates():
    cfg = {
        "modes": {"full": {"enabled_mates": ["m1", "m2", "position_mgr"], "rounds": 3}},
        "mates": {
            "m1": {"enabled": True, "model": "deepseek-chat"},
            "m2": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    mates = {"m1": _mock_mate("m1"), "m2": _mock_mate("m2"),
             "position_mgr": _mock_mate("position_mgr")}
    red_team = _mock_mate("red_team", view="空", confidence=60)
    red_team.run_rebuttal = MagicMock(return_value={"mate": "red_team", "view": "空", "extra": {}})
    decision_lead = MagicMock()
    decision_lead.synthesize.return_value = {"direction": "多", "confidence": 65}

    audit = MagicMock()
    audit.start_session.return_value = "audit-1"
    llm = MagicMock()
    from agent_system.providers.base import LLMResponse
    llm.chat.return_value = LLMResponse(text='{"keeps_view":true,"updated_confidence":70,"note":"x"}',
                                         usage={"total_tokens": 1}, model="deepseek-chat", raw={})
    orch = Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=red_team,
                        decision_lead=decision_lead, audit_logger=audit)
    pack = {"symbol": "ETHUSDT", "tags": []}
    card = orch.run(symbol="ETHUSDT", mode="full", data_pack=pack)

    assert mates["m1"].run.called
    assert mates["m2"].run.called
    assert mates["position_mgr"].run.called
    assert decision_lead.synthesize.called
    assert card["direction"] == "多"

def test_position_mgr_runs_after_other_mates():
    """position_mgr 必须在其他 Mate 完成后才能拿到 round_1_reports"""
    call_order = []
    def m_run(name):
        def _run(*args, **kwargs):
            call_order.append(name)
            return {"mate": name, "view": "多", "confidence": 70, "evidence": [], "extra": {}}
        return _run

    cfg = {
        "modes": {"full": {"enabled_mates": ["m1", "position_mgr"], "rounds": 3}},
        "mates": {
            "m1": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    m1 = MagicMock(); m1.run.side_effect = m_run("m1")
    pm = MagicMock(); pm.run.side_effect = m_run("position_mgr")
    rt = MagicMock(); rt.run_rebuttal = MagicMock(return_value={"mate":"red_team", "extra":{}})
    rt.run = MagicMock(return_value={"mate":"red_team","view":"观望","confidence":0,"evidence":[],"extra":{}})
    dl = MagicMock(); dl.synthesize.return_value = {"direction": "多"}
    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    from agent_system.providers.base import LLMResponse
    llm.chat.return_value = LLMResponse(text='{"keeps_view":true}', usage={}, model="x", raw={})

    orch = Orchestrator(cfg=cfg, llm_client=llm, mates={"m1": m1, "position_mgr": pm},
                        red_team=rt, decision_lead=dl, audit_logger=audit)
    orch.run(symbol="ETHUSDT", mode="full", data_pack={"symbol": "ETHUSDT", "tags": []})
    assert call_order.index("m1") < call_order.index("position_mgr")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_orchestrator.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `core/orchestrator.py`**

```python
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime

ROUND_2_RESPONSE_PROMPT = """你是 {mate_name} 分析师。第 1 轮你的判断是:
{your_round_1_json}

蒋军(Red Team)对多数派(view={majority_view})的反驳如下:
{rebuttal_json}

请基于反驳和原始数据,决定是否坚持原观点。如果反驳有据,适当下调 confidence 或修正 view。
严格输出 JSON:
{{
  "mate": "{mate_name}",
  "keeps_view": <true|false>,
  "updated_view": "<多|空|观望>",
  "updated_confidence": <0-100>,
  "note": "<一句话解释>"
}}

只输出 JSON,不要 Markdown,不要其他文字。"""

class Orchestrator:
    def __init__(self, cfg, llm_client, mates, red_team=None, decision_lead=None,
                 audit_logger=None):
        self.cfg = cfg
        self.llm = llm_client
        self.mates = mates
        self.red_team = red_team
        self.decision_lead = decision_lead
        self.audit = audit_logger

    def _enabled_mates_for_mode(self, mode: str) -> list[str]:
        mode_cfg = self.cfg["modes"][mode]
        mode_list = mode_cfg["enabled_mates"]
        mates_cfg = self.cfg["mates"]
        return [m for m in mode_list if mates_cfg.get(m, {}).get("enabled", False)]

    def _run_round_1_batch_1(self, mate_names: list[str], data_pack: dict, audit_id: str) -> list[dict]:
        results = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {
                ex.submit(self.mates[n].run, data_pack, None, self.audit, audit_id, 1): n
                for n in mate_names
            }
            for f in as_completed(futures):
                results.append(f.result())

        if self.red_team is not None and "red_team" not in mate_names:
            rt_result = self.red_team.run(data_pack, None, self.audit, audit_id, 1)
            results.append(rt_result)
        return results

    def _run_round_1_batch_2(self, data_pack: dict, batch_1_results: list[dict],
                              audit_id: str) -> dict:
        if "position_mgr" not in self.mates:
            return None
        return self.mates["position_mgr"].run(
            data_pack, extra_ctx={"round_1_reports_json": batch_1_results},
            audit_logger=self.audit, audit_id=audit_id, round_num=1,
        )

    def _majority_view(self, reports: list[dict]) -> str:
        views = [r.get("view") for r in reports if r.get("view") in ("多", "空")]
        if not views:
            return "观望"
        return Counter(views).most_common(1)[0][0]

    def _respond_to_rebuttal(self, mate_name: str, your_round_1: dict, rebuttal: dict,
                              majority_view: str, audit_id: str) -> dict:
        """被点名 Mate 回应反驳: 走统一 LLM prompt, 不调用 Mate.run"""
        prompt = ROUND_2_RESPONSE_PROMPT.format(
            mate_name=mate_name,
            your_round_1_json=json.dumps(your_round_1, ensure_ascii=False),
            majority_view=majority_view,
            rebuttal_json=json.dumps(rebuttal, ensure_ascii=False),
        )
        model = self.cfg["mates"].get(mate_name, {}).get("model") or self.cfg.get("default_model", "deepseek-chat")
        start = time.time()
        try:
            resp = self.llm.chat(model=model, messages=[{"role": "user", "content": prompt}],
                                  temperature=0.3, max_tokens=500, response_format="json")
            duration_ms = int((time.time() - start) * 1000)
            try:
                m = re.search(r'\{.*\}', resp.text, re.DOTALL)
                parsed = json.loads(m.group(0) if m else resp.text)
            except Exception:
                parsed = {"mate": mate_name, "keeps_view": True, "note": "(parse failed)",
                          "_raw": resp.text[:500]}
            if self.audit and audit_id:
                self.audit.log_call(audit_id=audit_id, round_num=2,
                                     mate=f"{mate_name}_response",
                                     model=model, prompt=prompt, response=resp.text,
                                     tokens=resp.usage, duration_ms=duration_ms)
            return parsed
        except Exception as e:
            return {"mate": mate_name, "keeps_view": True, "note": f"(call failed: {e})"}

    def _run_round_2(self, data_pack: dict, round_1_reports: list[dict],
                     audit_id: str) -> dict:
        if self.red_team is None:
            return {"rebuttal": None, "responses": [], "majority": "观望"}
        majority = self._majority_view(round_1_reports)
        rebuttal = self.red_team.run_rebuttal(
            data_pack=data_pack, round_1_reports=round_1_reports,
            majority_view=majority, audit_logger=self.audit, audit_id=audit_id,
        )
        majority_reports = [r for r in round_1_reports if r.get("view") == majority]
        majority_reports.sort(key=lambda r: r.get("confidence", 0), reverse=True)
        top3 = majority_reports[:3]
        responses = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = []
            for r in top3:
                mate_name = r.get("mate")
                if not mate_name:
                    continue
                futures.append(ex.submit(
                    self._respond_to_rebuttal, mate_name, r, rebuttal, majority, audit_id
                ))
            for f in as_completed(futures):
                responses.append(f.result())
        return {"rebuttal": rebuttal, "responses": responses, "majority": majority}

    def _run_round_3(self, data_pack: dict, round_1_reports: list[dict],
                     round_2_debate: dict, audit_id: str) -> dict:
        if self.decision_lead is None:
            return {"direction": "观望", "_error": "decision_lead 未注册"}
        return self.decision_lead.synthesize(
            data_pack=data_pack, round_1_reports=round_1_reports,
            round_2_debate=round_2_debate, audit_logger=self.audit, audit_id=audit_id,
        )

    def run(self, symbol: str, mode: str, data_pack: dict, session_key: str = None) -> dict:
        if session_key is None:
            session_key = f"{symbol}_{int(datetime.now().timestamp())}"
        audit_id = self.audit.start_session(prefix="decision", session_key=session_key) if self.audit else None
        rounds = self.cfg["modes"][mode].get("rounds", 3)

        enabled = self._enabled_mates_for_mode(mode)
        batch_1_mates = [m for m in enabled if m != "position_mgr"]
        batch_1_results = self._run_round_1_batch_1(batch_1_mates, data_pack, audit_id)

        if "position_mgr" in enabled:
            position_mgr_result = self._run_round_1_batch_2(data_pack, batch_1_results, audit_id)
            if position_mgr_result:
                batch_1_results.append(position_mgr_result)

        round_2_debate = {"rebuttal": None, "responses": [], "majority": "观望"}
        if rounds >= 3:
            round_2_debate = self._run_round_2(data_pack, batch_1_results, audit_id)

        card = self._run_round_3(data_pack, batch_1_results, round_2_debate, audit_id)

        if self.audit and audit_id:
            self.audit.finalize(audit_id, final_card=card)
        return card
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/core/orchestrator.py agent_system/tests/test_orchestrator.py
git commit -m "feat: orchestrator 三轮辩论编排(Batch 1/2 + Round 2/3)"
```

---

### Task 2.4: 扩展 config.yaml 启用全部 11 Mate

**Files:**
- Modify: `agent_system/config.yaml`

- [ ] **Step 1: 替换 config.yaml 中 mates 与 modes 部分为完整版**

把 mates 部分扩展为：

```yaml
mates:
  trend_multi_tf:
    model: deepseek-chat
    temperature: 0.2
    max_tokens: 1500
    enabled: true
    prompt_file: prompts/trend_multi_tf.md
  funding_rate:
    model: deepseek-chat
    temperature: 0.2
    max_tokens: 1000
    enabled: true
    prompt_file: prompts/funding_rate.md
  smart_money:
    model: deepseek-chat
    enabled: true
    prompt_file: prompts/smart_money.md
  long_short_compare:
    model: deepseek-chat
    enabled: true
    prompt_file: prompts/long_short_compare.md
  volatility:
    model: deepseek-chat
    enabled: true
    prompt_file: prompts/volatility.md
  experience:
    model: deepseek-chat
    temperature: 0.3
    enabled: false
    prompt_file: prompts/experience.md
  red_team:
    model: deepseek-chat
    temperature: 0.5
    enabled: true
    prompt_file: prompts/red_team.md
  macro_sentiment:
    model: deepseek-chat
    enabled: true
    prompt_file: prompts/macro_sentiment.md
  liquidity:
    model: deepseek-chat
    enabled: true
    prompt_file: prompts/liquidity.md
  position_mgr:
    model: deepseek-chat
    temperature: 0.1
    enabled: true
    prompt_file: prompts/position_mgr.md
  decision_lead:
    model: deepseek-chat
    temperature: 0.2
    enabled: true
    prompt_file: prompts/decision_lead.md

modes:
  full:
    enabled_mates: [trend_multi_tf, funding_rate, smart_money,
                    long_short_compare, volatility, experience,
                    red_team, macro_sentiment, liquidity,
                    position_mgr]
    rounds: 3
  lean:
    enabled_mates: [trend_multi_tf, funding_rate, smart_money,
                    long_short_compare, red_team, position_mgr,
                    experience]
    rounds: 2
  tracking:
    enabled_mates: [trend_multi_tf, funding_rate, smart_money,
                    long_short_compare, red_team, position_mgr,
                    experience]
    rounds: 2
```

- [ ] **Step 2: Commit**

```bash
git add agent_system/config.yaml
git commit -m "feat: config 启用全部 11 Mate + 三种 mode 档位"
```

---

### Task 2.5: CLI dry_run 支持 --mode 完整流程

**Files:**
- Modify: `agent_system/cli/__main__.py`

- [ ] **Step 1: 扩展 `cli/__main__.py`**

替换 `_register_mate_classes` 与 `cmd_dry_run` 函数：

```python
def _register_mate_classes():
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

def _build_orchestrator(cfg, llm, prompts_dir, audit_dir):
    from agent_system.core.orchestrator import Orchestrator
    from agent_system.core.audit_logger import AuditLogger
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

def cmd_dry_run(args):
    _register_mate_classes()
    cfg = load_config(args.config)
    llm = _build_llm_client(cfg)
    binance = _build_binance(cfg)
    prompts_dir = str(Path(args.config).parent / "prompts")
    audit_dir = cfg.get("audit_dir", "tracks/")

    print(f"[1/3] Fetching data for {args.symbol}...")
    pack = build_pack(args.symbol, binance=binance, peer_symbols=args.peers or [])
    print(f"  → tags: {pack['tags']}, price_now: {pack['price_now']}")

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
        orch = _build_orchestrator(cfg, llm, prompts_dir, audit_dir)
        print(f"[2/3] Running orchestrator mode='{args.mode}'...")
        card = orch.run(symbol=args.symbol, mode=args.mode, data_pack=pack)
        print("[3/3] Decision card:")
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print("Provide --mate or --mode")
```

- [ ] **Step 2: 端到端验证完整 full 模式**

Run: `python -m agent_system.cli dry_run --symbol ETHUSDT --mode full`
Expected:
- 输出 `[1/3] Fetching data...`
- 输出 `[2/3] Running orchestrator mode='full'...`
- 大约 20-30 秒后输出决策卡片 JSON,含 direction、entry_price、stop_loss、take_profit、confidence、key_evidence、key_risks、execution_plan
- 在 `tracks/` 下出现 `decision_ETHUSDT_<timestamp>.json` 审计文件,内含 3 轮调用记录

- [ ] **Step 3: 验证 lean 与 tracking 模式**

Run: `python -m agent_system.cli dry_run --symbol BTCUSDT --mode lean`
Expected: 较 full 模式快(2 轮),决策卡片仍合法

- [ ] **Step 4: Commit**

```bash
git add agent_system/cli/__main__.py
git commit -m "feat: CLI dry_run --mode 跑通完整 11 Mate 三轮辩论"
```

---

### Task 2.6: 集成测试（可选 mock，验证编排稳定性）

**Files:**
- Create: `agent_system/tests/integration/test_full_mode_dry_run.py`

- [ ] **Step 1: 写集成测试（用 mock LLM 避免实际打 API）**

```python
import json
from unittest.mock import MagicMock
from agent_system.core.orchestrator import Orchestrator
from agent_system.providers.base import LLMResponse

def _build_mock_mate(name):
    from agent_system.mates.base import BaseMate
    class _M(BaseMate):
        def run(self, data_pack, extra_ctx=None, audit_logger=None, audit_id=None, round_num=1):
            return {"mate": name, "view": "多", "confidence": 70, "evidence": ["mock"], "extra": {}}
    return _M(name=name, llm_client=None, mate_cfg={"model": "deepseek-chat", "prompt_file": ""}, prompts_dir="")

def test_full_mode_end_to_end_with_mocks():
    cfg = {
        "modes": {"full": {"enabled_mates": ["trend_multi_tf", "funding_rate",
                                              "smart_money", "position_mgr"], "rounds": 3}},
        "mates": {
            "trend_multi_tf": {"enabled": True, "model": "deepseek-chat"},
            "funding_rate": {"enabled": True, "model": "deepseek-chat"},
            "smart_money": {"enabled": True, "model": "deepseek-chat"},
            "position_mgr": {"enabled": True, "model": "deepseek-chat"},
            "red_team": {"enabled": True, "model": "deepseek-chat"},
            "decision_lead": {"enabled": True, "model": "deepseek-chat"},
        },
        "default_model": "deepseek-chat",
    }
    mates = {n: _build_mock_mate(n) for n in ["trend_multi_tf", "funding_rate", "smart_money", "position_mgr"]}

    rt = MagicMock()
    rt.run = MagicMock(return_value={"mate": "red_team", "view": "空", "confidence": 50, "evidence": [], "extra": {}})
    rt.run_rebuttal = MagicMock(return_value={"mate": "red_team", "view": "空", "extra": {"rebuttal": "..."}})

    dl = MagicMock()
    dl.synthesize.return_value = {
        "direction": "多", "entry_price": 3120, "stop_loss": 3050, "take_profit": 3260,
        "confidence": 65, "key_evidence": ["e1"], "key_risks": ["r1"],
    }

    audit = MagicMock(); audit.start_session.return_value = "a"
    llm = MagicMock()
    from agent_system.providers.base import LLMResponse
    llm.chat.return_value = LLMResponse(text='{"keeps_view":true}', usage={}, model="x", raw={})
    orch = Orchestrator(cfg=cfg, llm_client=llm, mates=mates, red_team=rt, decision_lead=dl, audit_logger=audit)
    card = orch.run(symbol="ETHUSDT", mode="full",
                    data_pack={"symbol": "ETHUSDT", "tags": []})
    assert card["direction"] == "多"
    assert card["confidence"] == 65
    assert audit.start_session.called
    assert audit.finalize.called
```

- [ ] **Step 2: 运行测试**

Run: `pytest agent_system/tests/integration/test_full_mode_dry_run.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add agent_system/tests/integration/
git commit -m "test: full 模式集成测试(mock LLM)"
```

---

## Phase 3 — Web 对话 + 三种触发模式

**目标**：上线对话主页（三栏布局），三种触发模式（chat/scan/tracking）都能产出推送。

### Task 3.1: data/decisions_store CRUD

**Files:**
- Create: `agent_system/data/decisions_store.py`
- Test: `agent_system/tests/test_decisions_store.py`

- [ ] **Step 1: 写失败的测试**

```python
import json
from agent_system.data.db import init_new_tables
from agent_system.data.decisions_store import save_decision, get_decision, list_open_decisions, update_decision_status

def test_save_and_get(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"symbol": "ETHUSDT", "direction": "多", "entry_price": 3120,
            "stop_loss": 3050, "take_profit": 3260, "confidence": 65,
            "key_evidence": ["e"], "key_risks": ["r"]}
    did = save_decision(db, symbol="ETHUSDT", trigger_mode="chat",
                        card=card, tags=["funding=normal"], audit_path="tracks/x.json")
    got = get_decision(db, did)
    assert got["symbol"] == "ETHUSDT"
    assert got["status"] == "open"
    assert got["direction"] == "多"
    assert json.loads(got["tags"]) == ["funding=normal"]

def test_list_open(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 1, "stop_loss": 1, "take_profit": 1, "confidence": 50,
            "key_evidence": [], "key_risks": []}
    save_decision(db, "A", "chat", card, [], "p")
    save_decision(db, "B", "scan", card, [], "p")
    open_list = list_open_decisions(db)
    assert len(open_list) == 2

def test_update_status(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 1, "stop_loss": 1, "take_profit": 1, "confidence": 50,
            "key_evidence": [], "key_risks": []}
    did = save_decision(db, "A", "chat", card, [], "p")
    update_decision_status(db, did, status="win", realized_pnl_pct=5.2)
    got = get_decision(db, did)
    assert got["status"] == "win"
    assert got["realized_pnl_pct"] == 5.2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_decisions_store.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `data/decisions_store.py`**

```python
import json
from datetime import datetime
from agent_system.data.db import get_conn

def save_decision(db_path, symbol, trigger_mode, card, tags, audit_path) -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO decisions (symbol, trigger_mode, direction, entry_price,
               stop_loss, take_profit, confidence, tags, card_json, audit_path,
               status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (symbol, trigger_mode, card.get("direction"),
             card.get("entry_price"), card.get("stop_loss"), card.get("take_profit"),
             card.get("confidence"), json.dumps(tags, ensure_ascii=False),
             json.dumps(card, ensure_ascii=False), audit_path,
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_decision(db_path, decision_id) -> dict:
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def list_open_decisions(db_path) -> list[dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM decisions WHERE status = 'open'").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_decision_status(db_path, decision_id, status, realized_pnl_pct=None):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """UPDATE decisions SET status = ?, closed_at = ?, realized_pnl_pct = ?
               WHERE decision_id = ?""",
            (status, datetime.now().isoformat(), realized_pnl_pct, decision_id),
        )
        conn.commit()
    finally:
        conn.close()

def list_recent_decisions(db_path, limit=50) -> list[dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY decision_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_decisions_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/data/decisions_store.py agent_system/tests/test_decisions_store.py
git commit -m "feat: decisions_store CRUD + 状态更新"
```

---

### Task 3.2: data/chat_store CRUD

**Files:**
- Create: `agent_system/data/chat_store.py`
- Test: `agent_system/tests/test_chat_store.py`

- [ ] **Step 1: 写失败的测试**

```python
from agent_system.data.db import init_new_tables
from agent_system.data.chat_store import save_message, list_messages

def test_save_and_list(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    save_message(db, "sess-1", "user", "hi", decision_id=None)
    save_message(db, "sess-1", "assistant", "hello", decision_id=42)
    msgs = list_messages(db, "sess-1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["decision_id"] == 42
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_chat_store.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `data/chat_store.py`**

```python
from datetime import datetime
from agent_system.data.db import get_conn

def save_message(db_path, session_id, role, content, decision_id=None) -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO chat_messages (session_id, role, content, decision_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, role, content, decision_id, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def list_messages(db_path, session_id) -> list[dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY msg_id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 4: 测试通过**

Run: `pytest agent_system/tests/test_chat_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/data/chat_store.py agent_system/tests/test_chat_store.py
git commit -m "feat: chat_store 对话历史 CRUD"
```

---

### Task 3.3: runners/chat_runner 意图解析 + 调度

**Files:**
- Create: `agent_system/runners/chat_runner.py`

- [ ] **Step 1: 实现 `runners/chat_runner.py`**

```python
import json
import re
from datetime import datetime
from agent_system.data.chat_store import save_message, list_messages
from agent_system.data.decisions_store import save_decision

INTENT_PROMPT = """你是意图解析器。识别用户消息的意图,输出 JSON。

可选意图:
- single_analysis: 用户希望分析某个币种的入场机会(包含币种或合约名)
- tracking_query: 用户询问已跟踪的持仓
- data_query: 用户询问某币种的简单数据(费率/价格等)
- chitchat: 闲聊或不属于以上

输出格式:
{"intent": "<意图>", "symbol": "<币种.如 ETHUSDT,无则 null>", "extra": {}}

用户消息: {{ user_text }}"""

def parse_intent(llm_client, model: str, user_text: str) -> dict:
    prompt = INTENT_PROMPT.replace("{{ user_text }}", user_text)
    resp = llm_client.chat(
        model=model, messages=[{"role": "user", "content": prompt}],
        temperature=0.1, max_tokens=200, response_format="json",
    )
    try:
        m = re.search(r'\{.*\}', resp.text, re.DOTALL)
        return json.loads(m.group(0) if m else resp.text)
    except Exception:
        return {"intent": "chitchat", "symbol": None, "extra": {}}

class ChatRunner:
    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer

    def handle_message(self, session_id: str, user_text: str, on_stage=None) -> dict:
        save_message(self.db_path, session_id, "user", user_text)
        intent_model = self.cfg.get("default_model", "deepseek-chat")
        intent = parse_intent(self.llm, intent_model, user_text)

        if on_stage:
            on_stage("intent", intent)

        if intent["intent"] == "single_analysis" and intent.get("symbol"):
            symbol = intent["symbol"]
            if on_stage:
                on_stage("data_packing", {"symbol": symbol})
            pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
            if on_stage:
                on_stage("orchestrator_start", {"symbol": symbol, "mode": "full"})
            card = self.orch.run(symbol=symbol, mode="full", data_pack=pack)
            tags = pack.get("tags", [])
            audit_path = card.get("audit_path") or ""
            decision_id = save_decision(
                self.db_path, symbol=symbol, trigger_mode="chat",
                card=card, tags=tags, audit_path=audit_path,
            )
            card["decision_id"] = decision_id
            save_message(self.db_path, session_id, "assistant",
                         json.dumps(card, ensure_ascii=False), decision_id=decision_id)
            if on_stage:
                on_stage("decision_card", card)
            return {"type": "decision_card", "card": card}

        elif intent["intent"] == "data_query" and intent.get("symbol"):
            return {"type": "data_query", "intent": intent,
                    "message": f"暂未实现 data_query 详细应答(intent: {intent})"}

        elif intent["intent"] == "tracking_query":
            return {"type": "tracking_query",
                    "message": "持仓跟踪查询(Phase 4 实现)"}

        else:
            return {"type": "chitchat",
                    "message": "我是币安合约智能体,可以帮你分析具体币种(例如:'帮我分析 ETH 是否有买卖点')。"}
```

- [ ] **Step 2: Commit**

```bash
git add agent_system/runners/chat_runner.py
git commit -m "feat: chat_runner 意图解析 + 调度 orchestrator"
```

---

### Task 3.4: runners/scan_runner 自带预筛器

**Files:**
- Create: `agent_system/runners/scan_runner.py`
- Test: `agent_system/tests/test_scan_prefilter.py`

预筛策略(替代旧 signals.py): 用币安 ticker 数据(24h 成交量 + 当前费率)做轻量筛选,得出候选币种。
- 取所有 USDT 永续合约 24h quoteVolume top 30
- 在 top 30 中再按费率绝对值排序,取 top 10
- 在 top 30 中再按持仓多空比偏离中性(=1.0)的程度排序,取另外 top 10
- 两组并集,去重后限 max_candidates 个

- [ ] **Step 1: 写预筛失败测试**

```python
from unittest.mock import MagicMock
from agent_system.runners.scan_runner import _prefilter_by_volume_and_extremes

def test_prefilter_combines_top_volume_funding_and_position():
    # 5 个币: A 体量最大但费率温和; B 中等体量+极端费率; C 中等体量+极端持仓多空比;
    # D 小体量(被筛掉); E 中等体量+正常 -> 不入选
    binance = MagicMock()
    binance.get_premium_index.return_value = [
        {"symbol": "AUSDT", "lastFundingRate": "0.0001"},
        {"symbol": "BUSDT", "lastFundingRate": "0.005"},
        {"symbol": "CUSDT", "lastFundingRate": "0.0002"},
        {"symbol": "EUSDT", "lastFundingRate": "0.0001"},
    ]
    # 不同 symbol 的 24h ticker 不同体量
    def fake_ticker():
        return [
            {"symbol": "AUSDT", "quoteVolume": "1000000000"},
            {"symbol": "BUSDT", "quoteVolume": "500000000"},
            {"symbol": "CUSDT", "quoteVolume": "400000000"},
            {"symbol": "EUSDT", "quoteVolume": "300000000"},
            {"symbol": "DUSDT", "quoteVolume": "100"},  # 太小, 排除
        ]
    binance.get_24h_ticker = fake_ticker
    # C 的大户多空比异常偏离
    def fake_top_pos(symbol, **kw):
        if symbol == "CUSDT":
            return [{"longShortRatio": "3.5", "timestamp": 1}]
        return [{"longShortRatio": "1.05", "timestamp": 1}]
    binance.get_top_long_short_position_ratio.side_effect = fake_top_pos

    candidates = _prefilter_by_volume_and_extremes(
        binance=binance, top_volume=4, top_funding=2, top_position_dev=2,
    )
    assert "BUSDT" in candidates  # 极端费率
    assert "CUSDT" in candidates  # 极端多空比
    assert "DUSDT" not in candidates  # 体量太小
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_scan_prefilter.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `runners/scan_runner.py`**

```python
from agent_system.data.decisions_store import save_decision

def _prefilter_by_volume_and_extremes(binance, top_volume=30, top_funding=10,
                                        top_position_dev=10):
    """简化预筛: 取体量 top N, 在其中再选费率/持仓多空比极端者并集。"""
    tickers = binance.get_24h_ticker()
    ticker_map = {t["symbol"]: float(t.get("quoteVolume", 0))
                   for t in tickers if t.get("symbol", "").endswith("USDT")}
    top_vol_symbols = sorted(ticker_map.keys(), key=lambda s: ticker_map[s], reverse=True)[:top_volume]

    funding = binance.get_premium_index()
    fmap = {f["symbol"]: float(f.get("lastFundingRate", 0))
             for f in funding if f.get("symbol") in top_vol_symbols}
    by_funding = sorted(fmap.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_funding]

    pos_dev = []
    for s in top_vol_symbols:
        try:
            pr = binance.get_top_long_short_position_ratio(s, period="1h", limit=1)
            ratio = float(pr[-1]["longShortRatio"]) if pr else 1.0
            pos_dev.append((s, abs(ratio - 1.0)))
        except Exception:
            continue
    by_pos = sorted(pos_dev, key=lambda kv: kv[1], reverse=True)[:top_position_dev]

    out = []
    for s, _ in by_funding + by_pos:
        if s not in out:
            out.append(s)
    return out

class ScanRunner:
    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer,
                 push_client=None):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer
        self.push = push_client

    def _candidates(self) -> list[str]:
        try:
            limit = self.cfg["scheduler"]["scan_max_candidates"]
            return _prefilter_by_volume_and_extremes(
                self.binance, top_volume=30, top_funding=10, top_position_dev=10
            )[:limit]
        except Exception as e:
            print(f"[scan] prefilter failed: {e}; fallback")
            return ["BTCUSDT", "ETHUSDT"]

    def run_once(self) -> list[dict]:
        candidates = self._candidates()
        print(f"[scan] candidates: {candidates}")
        cards = []
        for symbol in candidates:
            try:
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                card = self.orch.run(symbol=symbol, mode="lean", data_pack=pack)
                tags = pack.get("tags", [])
                did = save_decision(self.db_path, symbol=symbol, trigger_mode="scan",
                                    card=card, tags=tags, audit_path="")
                card["decision_id"] = did
                cards.append(card)
            except Exception as e:
                print(f"[scan] {symbol} failed: {e}")
        cards.sort(key=lambda c: c.get("confidence", 0), reverse=True)
        top = cards[:5]
        if self.push and top:
            self.push.push_scan_results(top)
        return top
```

- [ ] **Step 4: 在 `data/binance_client.py` 增加 `get_24h_ticker` 方法**

```python
    def get_24h_ticker(self):
        url = f"{self.BASE_URL}/fapi/v1/ticker/24hr"
        r = requests.get(url, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 5: 测试通过**

Run: `pytest agent_system/tests/test_scan_prefilter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent_system/runners/scan_runner.py agent_system/data/binance_client.py agent_system/tests/test_scan_prefilter.py
git commit -m "feat: scan_runner 自带预筛器(成交量+费率/持仓极端度)"
```

---

### Task 3.5: data/tracking_store + runners/tracking_runner

**Files:**
- Create: `agent_system/data/tracking_store.py`
- Create: `agent_system/runners/tracking_runner.py`
- Test: `agent_system/tests/test_tracking_store.py`

- [ ] **Step 1: 写跟踪 CRUD 失败测试**

```python
import json
from agent_system.data.db import init_new_tables
from agent_system.data.tracking_store import (
    add_tracked_position, get_active_tracks, close_tracked_position,
    save_track_snapshot, list_track_history,
)

def test_add_and_list_active(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tid = add_tracked_position(db, symbol="ETHUSDT", direction="多",
                                entry_price=3120, stop_loss=3050, take_profit=3260,
                                entry_signals="trend+smart_money")
    active = get_active_tracks(db)
    assert len(active) == 1
    assert active[0]["id"] == tid
    assert active[0]["status"] == "active"

def test_close(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tid = add_tracked_position(db, "ETHUSDT", "多", 3120, 3050, 3260, "")
    close_tracked_position(db, tid, reason="manual")
    active = get_active_tracks(db)
    assert len(active) == 0

def test_save_and_list_snapshots(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    tid = add_tracked_position(db, "ETHUSDT", "多", 3120, 3050, 3260, "")
    save_track_snapshot(db, tid, snapshot={"price": 3150, "pnl": 0.96})
    save_track_snapshot(db, tid, snapshot={"price": 3170, "pnl": 1.6})
    rows = list_track_history(db, tid)
    assert len(rows) == 2
    assert json.loads(rows[0]["snapshot_json"])["price"] == 3150
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_tracking_store.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `data/tracking_store.py`**

```python
import json
from datetime import datetime
from agent_system.data.db import get_conn

def add_tracked_position(db_path, symbol, direction, entry_price,
                          stop_loss, take_profit, entry_signals="", notes="") -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO tracked_positions
               (symbol, direction, entry_price, stop_loss, take_profit,
                status, created_at, entry_signals, notes)
               VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
            (symbol, direction, entry_price, stop_loss, take_profit,
             datetime.now().isoformat(), entry_signals, notes),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def get_active_tracks(db_path) -> list[dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tracked_positions WHERE status = 'active'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def close_tracked_position(db_path, track_id, reason: str = ""):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """UPDATE tracked_positions
               SET status = 'closed', closed_at = ?, close_reason = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), reason, track_id),
        )
        conn.commit()
    finally:
        conn.close()

def save_track_snapshot(db_path, track_id, snapshot: dict):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """INSERT INTO track_history (track_id, snapshot_json, created_at)
               VALUES (?, ?, ?)""",
            (track_id, json.dumps(snapshot, ensure_ascii=False, default=str),
             datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

def list_track_history(db_path, track_id, limit=50) -> list[dict]:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM track_history WHERE track_id = ?
               ORDER BY id DESC LIMIT ?""",
            (track_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 4: 测试通过**

Run: `pytest agent_system/tests/test_tracking_store.py -v`
Expected: PASS

- [ ] **Step 5: 实现 `runners/tracking_runner.py`**

```python
from datetime import datetime
from agent_system.data.tracking_store import get_active_tracks, save_track_snapshot

class TrackingRunner:
    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer,
                 push_client=None):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer
        self.push = push_client

    def _build_tracking_context(self, track: dict) -> dict:
        return {
            "track_id": track.get("id"),
            "entry_price": track.get("entry_price"),
            "direction": track.get("direction"),
            "stop_loss": track.get("stop_loss"),
            "take_profit": track.get("take_profit"),
            "entry_signals": track.get("entry_signals"),
        }

    def run_once(self) -> list[dict]:
        tracks = get_active_tracks(self.db_path)
        print(f"[tracking] active tracks: {len(tracks)}")
        results = []
        for t in tracks:
            symbol = t.get("symbol")
            try:
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                pack["tracking_context"] = self._build_tracking_context(t)
                card = self.orch.run(
                    symbol=symbol, mode="tracking", data_pack=pack,
                    session_key=f"track_{t.get('id')}_{int(datetime.now().timestamp())}",
                )
                save_track_snapshot(self.db_path, t["id"],
                                     snapshot={"card": card, "price_now": pack.get("price_now")})
                results.append({"track": t, "card": card})
                if self.push:
                    self.push.push_tracking_update(t, card)
            except Exception as e:
                print(f"[tracking] {symbol} failed: {e}")
        return results
```

- [ ] **Step 6: Commit**

```bash
git add agent_system/data/tracking_store.py agent_system/runners/tracking_runner.py agent_system/tests/test_tracking_store.py
git commit -m "feat: tracking_store CRUD + tracking_runner(自带跟踪 DB,不依赖旧代码)"
```

---

### Task 3.6: push/server_chan 推送

**Files:**
- Create: `agent_system/push/server_chan.py`

- [ ] **Step 1: 实现 `push/server_chan.py`**

```python
import os
import requests

class ServerChanPush:
    def __init__(self, send_key_env: str = "SERVER_CHAN_KEY"):
        self.send_key = os.environ.get(send_key_env, "")
        self.enabled = bool(self.send_key)

    def _post(self, title: str, desp: str):
        if not self.enabled:
            print(f"[push] disabled (no SEND_KEY); title={title}")
            return
        url = f"https://sctapi.ftqq.com/{self.send_key}.send"
        try:
            requests.post(url, data={"title": title[:32], "desp": desp[:32000]}, timeout=15)
        except Exception as e:
            print(f"[push] failed: {e}")

    def _format_card(self, card: dict) -> str:
        if card.get("direction") == "观望":
            return (f"### {card.get('symbol')} 观望\n\n"
                    f"**Confidence:** {card.get('confidence', 0)}\n\n"
                    f"**Evidence:**\n" +
                    "\n".join(f"- {e}" for e in card.get("key_evidence", [])) +
                    "\n\n**Risks:**\n" +
                    "\n".join(f"- {r}" for r in card.get("key_risks", [])))
        return (
            f"### {card.get('symbol')} {card.get('direction')}\n\n"
            f"**Entry:** {card.get('entry_price')} (zone: {card.get('entry_zone')})\n"
            f"**SL:** {card.get('stop_loss')} | **TP:** {card.get('take_profit')}\n"
            f"**RR:** {card.get('risk_reward_ratio')} | **Position:** {card.get('position_size_pct')}%\n"
            f"**Confidence:** {card.get('confidence')}\n\n"
            f"**Evidence:**\n" + "\n".join(f"- {e}" for e in card.get("key_evidence", [])) +
            f"\n\n**Risks:**\n" + "\n".join(f"- {r}" for r in card.get("key_risks", [])) +
            f"\n\n**Plan:** {card.get('execution_plan', '')}"
        )

    def push_scan_results(self, cards: list[dict]):
        if not cards:
            return
        title = f"扫描决策 {len(cards)} 个"
        desp = "\n\n---\n\n".join(self._format_card(c) for c in cards)
        self._post(title, desp)

    def push_tracking_update(self, track: dict, card: dict):
        title = f"跟踪 {track.get('symbol')} {card.get('direction', '')}"
        desp = self._format_card(card) + f"\n\n**Track ID:** {track.get('id')}"
        self._post(title, desp)

    def push_chat_decision(self, card: dict):
        title = f"对话决策 {card.get('symbol')} {card.get('direction', '')}"
        self._post(title, self._format_card(card))
```

- [ ] **Step 2: Commit**

```bash
git add agent_system/push/server_chan.py
git commit -m "feat: server_chan 推送决策卡片(scan/tracking/chat)"
```

---

### Task 3.7: web/app.py + chat_api SSE

**Files:**
- Create: `agent_system/web/app.py`
- Create: `agent_system/web/chat_api.py`
- Create: `agent_system/web/debate_api.py`

- [ ] **Step 1: 实现 `web/chat_api.py`**

```python
import json
import queue
import threading
import uuid
from flask import Blueprint, request, jsonify, Response

bp = Blueprint("chat", __name__)

# 全局事件队列(简单实现,单进程)
_session_queues = {}

def init_chat_api(chat_runner):
    @bp.route("/api/chat", methods=["POST"])
    def chat():
        body = request.get_json(force=True)
        session_id = body.get("session_id") or str(uuid.uuid4())
        text = body["text"]
        q = _session_queues.setdefault(session_id, queue.Queue())

        def on_stage(name, payload):
            q.put({"stage": name, "payload": payload})

        def _bg():
            try:
                result = chat_runner.handle_message(session_id, text, on_stage=on_stage)
                q.put({"stage": "done", "payload": result})
            except Exception as e:
                q.put({"stage": "error", "payload": {"error": str(e)}})

        threading.Thread(target=_bg, daemon=True).start()
        return jsonify({"session_id": session_id})

    @bp.route("/api/chat/stream/<session_id>")
    def stream(session_id):
        def gen():
            q = _session_queues.setdefault(session_id, queue.Queue())
            while True:
                try:
                    evt = q.get(timeout=120)
                except queue.Empty:
                    yield "event: heartbeat\ndata: {}\n\n"
                    continue
                yield f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
                if evt.get("stage") in ("done", "error"):
                    break

        return Response(gen(), mimetype="text/event-stream")

    return bp
```

- [ ] **Step 2: 实现 `web/debate_api.py`** (查询历史决策审计)

```python
import json
from pathlib import Path
from flask import Blueprint, jsonify

bp = Blueprint("debate", __name__)

def init_debate_api(audit_dir):
    @bp.route("/api/debate/<int:decision_id>")
    def get_debate(decision_id):
        from agent_system.data.decisions_store import get_decision
        from flask import current_app
        db_path = current_app.config["DB_PATH"]
        d = get_decision(db_path, decision_id)
        if not d:
            return jsonify({"error": "not found"}), 404
        audit_path = d.get("audit_path") or ""
        audit_data = None
        if audit_path and Path(audit_path).exists():
            audit_data = json.loads(Path(audit_path).read_text(encoding="utf-8"))
        return jsonify({"decision": d, "audit": audit_data})

    return bp
```

- [ ] **Step 3: 实现 `web/app.py`**

```python
from pathlib import Path
from flask import Flask, render_template

def create_app(cfg, chat_runner, audit_dir, db_path):
    template_dir = Path(__file__).parent / "templates"
    static_dir = Path(__file__).parent / "static"
    app = Flask(__name__, template_folder=str(template_dir), static_folder=str(static_dir))
    app.config["DB_PATH"] = db_path
    app.config["AUDIT_DIR"] = audit_dir

    from agent_system.web.chat_api import init_chat_api
    from agent_system.web.debate_api import init_debate_api
    app.register_blueprint(init_chat_api(chat_runner))
    app.register_blueprint(init_debate_api(audit_dir))

    @app.route("/")
    def index():
        return render_template("chat.html")

    @app.route("/api/decisions")
    def list_decisions():
        from agent_system.data.decisions_store import list_recent_decisions
        from flask import jsonify
        return jsonify(list_recent_decisions(db_path, limit=50))

    return app
```

- [ ] **Step 4: Commit**

```bash
git add agent_system/web/app.py agent_system/web/chat_api.py agent_system/web/debate_api.py
git commit -m "feat: Flask app + 对话 API(SSE) + 决策审计 API"
```

---

### Task 3.8: web/templates/chat.html 三栏布局

**Files:**
- Create: `agent_system/web/templates/chat.html`
- Create: `agent_system/web/static/chat.css`
- Create: `agent_system/web/static/chat.js`

- [ ] **Step 1: 创建 `chat.html`**

```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <title>Agent Team 量化分析</title>
  <link rel="stylesheet" href="/static/chat.css">
</head>
<body>
  <div class="layout">
    <aside class="left">
      <h3>最近决策</h3>
      <ul id="decisions-list"></ul>
    </aside>
    <main class="center">
      <div id="messages"></div>
      <form id="chat-form">
        <input id="chat-input" placeholder="例: 帮我分析 ETH 是否有买卖点" autocomplete="off">
        <button type="submit">发送</button>
      </form>
    </main>
    <aside class="right">
      <h3>辩论流</h3>
      <div id="debate-stream"></div>
    </aside>
  </div>
  <script src="/static/chat.js"></script>
</body>
</html>
```

- [ ] **Step 2: 创建 `chat.css`**

```css
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; height: 100vh; background: #f5f5f5; }
.layout { display: grid; grid-template-columns: 240px 1fr 320px; height: 100vh; }
aside, main { padding: 12px; overflow-y: auto; background: #fff; border-left: 1px solid #eee; }
aside.left { border-left: 0; border-right: 1px solid #eee; }
h3 { font-size: 14px; margin-bottom: 8px; color: #666; }
#messages { height: calc(100vh - 60px); overflow-y: auto; padding: 12px; }
#chat-form { display: flex; gap: 8px; padding: 8px; border-top: 1px solid #eee; }
#chat-input { flex: 1; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
button { padding: 8px 16px; background: #2563eb; color: #fff; border: 0; border-radius: 4px; cursor: pointer; }
.msg { margin-bottom: 12px; padding: 8px 12px; border-radius: 6px; max-width: 80%; }
.msg.user { background: #dbeafe; margin-left: auto; }
.msg.assistant { background: #f3f4f6; }
.card { background: #fff; border: 1px solid #ddd; padding: 12px; border-radius: 8px; }
.card .dir { font-weight: bold; font-size: 18px; margin-bottom: 8px; }
.card .dir.long { color: #16a34a; }
.card .dir.short { color: #dc2626; }
.card .dir.wait { color: #6b7280; }
.stream-evt { padding: 6px; border-bottom: 1px solid #eee; font-size: 12px; }
.stream-evt .stage { font-weight: bold; color: #2563eb; }
#decisions-list { list-style: none; }
#decisions-list li { padding: 6px; border-bottom: 1px solid #eee; cursor: pointer; font-size: 13px; }
#decisions-list li:hover { background: #f9fafb; }
```

- [ ] **Step 3: 创建 `chat.js`**

```javascript
const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const streamEl = document.getElementById("debate-stream");
const listEl = document.getElementById("decisions-list");

let sessionId = null;

function appendMsg(role, content) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  if (typeof content === "object") {
    div.appendChild(renderCard(content));
  } else {
    div.textContent = content;
  }
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderCard(card) {
  const root = document.createElement("div");
  root.className = "card";
  const dirClass = card.direction === "多" ? "long" : card.direction === "空" ? "short" : "wait";
  root.innerHTML = `
    <div class="dir ${dirClass}">${card.symbol || ""} ${card.direction || ""} (信心 ${card.confidence ?? "-"})</div>
    <div><b>入场:</b> ${card.entry_price ?? "-"} (zone: ${JSON.stringify(card.entry_zone || [])})</div>
    <div><b>止损/止盈:</b> ${card.stop_loss ?? "-"} / ${card.take_profit ?? "-"} (RR ${card.risk_reward_ratio ?? "-"})</div>
    <div><b>仓位:</b> ${card.position_size_pct ?? "-"}%</div>
    <div><b>依据:</b><ul>${(card.key_evidence || []).map(e => `<li>${e}</li>`).join("")}</ul></div>
    <div><b>风险:</b><ul>${(card.key_risks || []).map(r => `<li>${r}</li>`).join("")}</ul></div>
    <div><b>计划:</b> ${card.execution_plan || ""}</div>
  `;
  return root;
}

function appendStreamEvent(evt) {
  const div = document.createElement("div");
  div.className = "stream-evt";
  div.innerHTML = `<span class="stage">${evt.stage}</span>: ${
    typeof evt.payload === "object" ? JSON.stringify(evt.payload).slice(0, 200) : evt.payload
  }`;
  streamEl.appendChild(div);
  streamEl.scrollTop = streamEl.scrollHeight;
}

async function send(text) {
  appendMsg("user", text);
  streamEl.innerHTML = "";
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({session_id: sessionId, text}),
  });
  const data = await r.json();
  sessionId = data.session_id;
  const es = new EventSource(`/api/chat/stream/${sessionId}`);
  es.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    appendStreamEvent(evt);
    if (evt.stage === "done") {
      const result = evt.payload;
      if (result.type === "decision_card") {
        appendMsg("assistant", result.card);
      } else {
        appendMsg("assistant", result.message || JSON.stringify(result));
      }
      es.close();
      loadDecisions();
    }
    if (evt.stage === "error") {
      appendMsg("assistant", "错误: " + JSON.stringify(evt.payload));
      es.close();
    }
  };
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  send(text);
});

async function loadDecisions() {
  const r = await fetch("/api/decisions");
  const list = await r.json();
  listEl.innerHTML = list.map(d =>
    `<li>${d.symbol} ${d.direction || ""} (${d.confidence ?? "-"}) ${d.status}</li>`
  ).join("");
}

loadDecisions();
```

- [ ] **Step 4: Commit**

```bash
git add agent_system/web/templates/ agent_system/web/static/
git commit -m "feat: chat.html 三栏布局 + SSE 流式辩论"
```

---

### Task 3.9: start.py 一键启动

**Files:**
- Create: `agent_system/start.py`

- [ ] **Step 1: 实现 `start.py`**

```python
import os
import signal
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

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
```

- [ ] **Step 2: 端到端验证**

确保环境变量都配齐。

Run: `python -m agent_system.start`
Expected:
- 输出 `[start] Web on http://localhost:5000`
- 浏览器打开 http://localhost:5000，看到三栏布局
- 输入"帮我分析 ETH"，几秒后右侧出现辩论流，最终中间出现决策卡片

- [ ] **Step 3: Commit**

```bash
git add agent_system/start.py
git commit -m "feat: start.py 一键启动 web + scan + tracking"
```

---

## Phase 4 — 决策记录 + 复盘冷启动

**目标**：决策入库（已在 Phase 3 完成），状态追踪，每日复盘，准备经验数据。**experience Mate 仍 enabled=false。**

### Task 4.1: runners/decision_status_tracker 状态追踪器

**Files:**
- Create: `agent_system/runners/decision_status_tracker.py`
- Test: `agent_system/tests/test_decision_status_tracker.py`

- [ ] **Step 1: 写失败的测试**

```python
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from agent_system.data.db import init_new_tables
from agent_system.data.decisions_store import save_decision, get_decision
from agent_system.runners.decision_status_tracker import DecisionStatusTracker

def test_marks_win_when_price_hits_take_profit(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    binance = MagicMock()
    binance.get_klines.return_value = [
        # 价格触达 110+
        [0, "100", "112", "99", "111", "1", 0, "1", 0, "1", "1", "0"],
    ]
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()
    got = get_decision(db, did)
    assert got["status"] == "win"
    assert got["realized_pnl_pct"] is not None and got["realized_pnl_pct"] > 0

def test_marks_loss_when_price_hits_stop_loss(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    binance = MagicMock()
    binance.get_klines.return_value = [
        # 价格跌破 95
        [0, "100", "100", "94", "94", "1", 0, "1", 0, "1", "1", "0"],
    ]
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()
    got = get_decision(db, did)
    assert got["status"] == "loss"
    assert got["realized_pnl_pct"] < 0

def test_marks_expired_after_timeout(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    card = {"direction": "多", "entry_price": 100, "stop_loss": 95, "take_profit": 110,
            "confidence": 70, "key_evidence": [], "key_risks": []}
    did = save_decision(db, "ETHUSDT", "chat", card, [], "")

    # 手动改 created_at 为 8 天前
    from agent_system.data.db import get_conn
    conn = get_conn(db)
    eight_days_ago = (datetime.now() - timedelta(days=8)).isoformat()
    conn.execute("UPDATE decisions SET created_at = ? WHERE decision_id = ?", (eight_days_ago, did))
    conn.commit(); conn.close()

    binance = MagicMock()
    binance.get_klines.return_value = [
        [0, "100", "102", "98", "101", "1", 0, "1", 0, "1", "1", "0"],
    ]
    tracker = DecisionStatusTracker(db_path=db, binance=binance, expire_days=7)
    tracker.run_once()
    got = get_decision(db, did)
    assert got["status"] == "expired"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_decision_status_tracker.py -v`
Expected: FAIL "ModuleNotFoundError"

- [ ] **Step 3: 实现 `runners/decision_status_tracker.py`**

```python
from datetime import datetime, timedelta
from agent_system.data.decisions_store import list_open_decisions, update_decision_status, get_decision
from agent_system.data.db import get_conn

class DecisionStatusTracker:
    def __init__(self, db_path: str, binance, expire_days: int = 7):
        self.db_path = db_path
        self.binance = binance
        self.expire_days = expire_days

    def _highest_low_in_window(self, symbol: str, since_iso: str):
        klines = self.binance.get_klines(symbol, interval="1h", limit=200)
        if not klines:
            return None, None
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        last_close = float(klines[-1][4])
        return max(highs), min(lows), last_close

    def _evaluate(self, decision: dict):
        direction = decision.get("direction")
        if direction not in ("多", "空"):
            return None  # 观望/其他不评估
        entry = decision.get("entry_price")
        sl = decision.get("stop_loss")
        tp = decision.get("take_profit")
        if entry is None or sl is None or tp is None:
            return None
        symbol = decision["symbol"]
        try:
            highest, lowest, last_close = self._highest_low_in_window(symbol, decision["created_at"])
        except Exception:
            return None
        if direction == "多":
            if lowest <= sl:
                pnl_pct = (sl - entry) / entry * 100
                return ("loss", pnl_pct)
            if highest >= tp:
                pnl_pct = (tp - entry) / entry * 100
                return ("win", pnl_pct)
        else:  # 空
            if highest >= sl:
                pnl_pct = (entry - sl) / entry * 100
                return ("loss", pnl_pct)
            if lowest <= tp:
                pnl_pct = (entry - tp) / entry * 100
                return ("win", pnl_pct)
        # 检查是否过期
        created = datetime.fromisoformat(decision["created_at"])
        if datetime.now() - created > timedelta(days=self.expire_days):
            if direction == "多":
                pnl_pct = (last_close - entry) / entry * 100
            else:
                pnl_pct = (entry - last_close) / entry * 100
            return ("expired", pnl_pct)
        return None

    def run_once(self):
        opens = list_open_decisions(self.db_path)
        for d in opens:
            result = self._evaluate(d)
            if result:
                status, pnl = result
                update_decision_status(self.db_path, d["decision_id"], status=status, realized_pnl_pct=pnl)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest agent_system/tests/test_decision_status_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/runners/decision_status_tracker.py agent_system/tests/test_decision_status_tracker.py
git commit -m "feat: decision_status_tracker 检查 open 决策状态(win/loss/expired)"
```

---

### Task 4.2: data/experience_store CRUD + 标签检索

**Files:**
- Create: `agent_system/data/experience_store.py`
- Test: `agent_system/tests/test_experience_store.py`

- [ ] **Step 1: 写失败的测试**

```python
import json
from agent_system.data.db import init_new_tables
from agent_system.data.experience_store import (
    create_experience, update_experience, find_by_tag_signature, search_by_tags,
)

def test_create_and_find(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    eid = create_experience(db,
        tags=["funding=extreme_high", "smart_money=divergence"],
        scenario_summary="高费率分歧",
        decisions_referenced=[1, 2],
        outcome_stats={"win": 1, "loss": 1, "expired": 0},
        lesson="..", applicable_when="..", caveats="..")
    e = find_by_tag_signature(db, ["funding=extreme_high", "smart_money=divergence"])
    assert e["experience_id"] == eid

def test_update(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    eid = create_experience(db, tags=["a"], scenario_summary="s",
                             decisions_referenced=[1], outcome_stats={"win": 1, "loss": 0, "expired": 0},
                             lesson="L1", applicable_when="", caveats="")
    update_experience(db, eid,
                       new_decision_ids=[2, 3],
                       new_outcome_stats={"win": 2, "loss": 1, "expired": 0},
                       new_lesson="L2")
    e = find_by_tag_signature(db, ["a"])
    assert json.loads(e["decisions_referenced"]) == [1, 2, 3]
    assert e["lesson"] == "L2"

def test_search_by_tags(tmp_path):
    db = str(tmp_path / "t.db")
    init_new_tables(db)
    create_experience(db, tags=["a", "b"], scenario_summary="",
                       decisions_referenced=[], outcome_stats={"win":0,"loss":0,"expired":0},
                       lesson="L1", applicable_when="", caveats="")
    create_experience(db, tags=["b", "c"], scenario_summary="",
                       decisions_referenced=[], outcome_stats={"win":0,"loss":0,"expired":0},
                       lesson="L2", applicable_when="", caveats="")
    matches = search_by_tags(db, query_tags=["b"], limit=5, days=90)
    assert len(matches) == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest agent_system/tests/test_experience_store.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `data/experience_store.py`**

```python
import json
from datetime import datetime, timedelta
from agent_system.data.db import get_conn

def create_experience(db_path, tags, scenario_summary, decisions_referenced,
                       outcome_stats, lesson, applicable_when, caveats) -> int:
    conn = get_conn(db_path)
    try:
        now = datetime.now().isoformat()
        cur = conn.execute(
            """INSERT INTO experiences (tags, scenario_summary, decisions_referenced,
               outcome_stats, lesson, applicable_when, caveats, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (json.dumps(sorted(tags), ensure_ascii=False), scenario_summary,
             json.dumps(decisions_referenced), json.dumps(outcome_stats),
             lesson, applicable_when, caveats, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def update_experience(db_path, eid, new_decision_ids=None, new_outcome_stats=None,
                       new_lesson=None, new_applicable_when=None, new_caveats=None):
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM experiences WHERE experience_id = ?", (eid,)).fetchone()
        if not row:
            return
        existing_ids = json.loads(row["decisions_referenced"] or "[]")
        if new_decision_ids:
            for did in new_decision_ids:
                if did not in existing_ids:
                    existing_ids.append(did)
        outcome = json.loads(row["outcome_stats"] or "{}")
        if new_outcome_stats:
            outcome = new_outcome_stats
        lesson = new_lesson if new_lesson is not None else row["lesson"]
        aw = new_applicable_when if new_applicable_when is not None else row["applicable_when"]
        cv = new_caveats if new_caveats is not None else row["caveats"]
        conn.execute(
            """UPDATE experiences SET decisions_referenced=?, outcome_stats=?,
               lesson=?, applicable_when=?, caveats=?, updated_at=?
               WHERE experience_id = ?""",
            (json.dumps(existing_ids), json.dumps(outcome), lesson, aw, cv,
             datetime.now().isoformat(), eid),
        )
        conn.commit()
    finally:
        conn.close()

def find_by_tag_signature(db_path, tags) -> dict:
    """精确匹配: 排序后的 tags 完全相等"""
    sig = json.dumps(sorted(tags), ensure_ascii=False)
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM experiences WHERE tags = ?", (sig,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def search_by_tags(db_path, query_tags, limit=5, days=90) -> list[dict]:
    """模糊匹配: 任一标签命中, 按命中数量倒序"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM experiences WHERE updated_at > ?", (cutoff,)
        ).fetchall()
        scored = []
        qset = set(query_tags)
        for r in rows:
            tags = set(json.loads(r["tags"] or "[]"))
            hit = len(tags & qset)
            if hit > 0:
                outcome = json.loads(r["outcome_stats"] or "{}")
                clarity = abs(outcome.get("win", 0) - outcome.get("loss", 0))
                scored.append((hit, clarity, dict(r)))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [s[2] for s in scored[:limit]]
    finally:
        conn.close()
```

- [ ] **Step 4: 测试通过**

Run: `pytest agent_system/tests/test_experience_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent_system/data/experience_store.py agent_system/tests/test_experience_store.py
git commit -m "feat: experience_store CRUD + 标签精确/模糊检索"
```

---

### Task 4.3: runners/retrospective_runner 每日复盘

**Files:**
- Create: `agent_system/runners/retrospective_runner.py`

- [ ] **Step 1: 实现 `runners/retrospective_runner.py`**

```python
import json
from collections import defaultdict
from datetime import datetime, timedelta
from agent_system.data.db import get_conn
from agent_system.data.experience_store import find_by_tag_signature, create_experience, update_experience

RETRO_PROMPT = """你是策略复盘官。基于以下已完结的决策列表(同一场景标签组),
1) 总结该场景的成败规律
2) 提炼 1 段 lesson(自然语言, 100-200 字)
3) 给出 applicable_when(触发条件,简洁)
4) 给出 caveats(失效条件)

输出严格 JSON:
{
  "scenario_summary": "<一句话场景描述>",
  "lesson": "<复盘文本>",
  "applicable_when": "<...>",
  "caveats": "<...>"
}

场景标签: {{ tags }}
该场景下的决策记录(已标注 win/loss/expired 与 realized_pnl_pct):
{{ decisions_json }}
"""

class RetrospectiveRunner:
    def __init__(self, cfg, llm_client, db_path, audit_logger=None):
        self.cfg = cfg
        self.llm = llm_client
        self.db_path = db_path
        self.audit = audit_logger

    def _closed_decisions_in_window(self, hours: int = 24) -> list[dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        conn = get_conn(self.db_path)
        try:
            rows = conn.execute(
                """SELECT * FROM decisions
                   WHERE status IN ('win','loss','expired')
                     AND closed_at > ?""", (cutoff,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _group_by_tags(self, decisions: list[dict]) -> dict:
        groups = defaultdict(list)
        for d in decisions:
            tags = sorted(json.loads(d.get("tags") or "[]"))
            groups[tuple(tags)].append(d)
        return dict(groups)

    def _llm_retro(self, tags: list, decisions: list[dict]) -> dict:
        prompt = RETRO_PROMPT.replace("{{ tags }}", json.dumps(tags, ensure_ascii=False))
        prompt = prompt.replace("{{ decisions_json }}", json.dumps(decisions, ensure_ascii=False, default=str))
        model = self.cfg.get("default_model", "deepseek-chat")
        resp = self.llm.chat(model=model, messages=[{"role": "user", "content": prompt}],
                             temperature=0.3, max_tokens=1500, response_format="json")
        try:
            import re
            m = re.search(r'\{.*\}', resp.text, re.DOTALL)
            return json.loads(m.group(0) if m else resp.text)
        except Exception:
            return {"scenario_summary": "(parse failed)", "lesson": resp.text[:500],
                    "applicable_when": "", "caveats": ""}

    def _outcome_stats(self, decisions: list[dict]) -> dict:
        stats = {"win": 0, "loss": 0, "expired": 0}
        for d in decisions:
            s = d.get("status")
            if s in stats:
                stats[s] += 1
        return stats

    def run_daily(self):
        closed = self._closed_decisions_in_window(hours=24)
        if not closed:
            print("[retro] no closed decisions in last 24h")
            return
        groups = self._group_by_tags(closed)
        for tags_tuple, decisions in groups.items():
            tags = list(tags_tuple)
            if not tags:
                continue
            existing = find_by_tag_signature(self.db_path, tags)
            retro = self._llm_retro(tags, decisions)
            outcome = self._outcome_stats(decisions)
            decision_ids = [d["decision_id"] for d in decisions]
            if existing:
                # 合并 outcome
                old_outcome = json.loads(existing["outcome_stats"] or "{}")
                merged = {k: old_outcome.get(k, 0) + outcome.get(k, 0) for k in ("win","loss","expired")}
                update_experience(
                    self.db_path, existing["experience_id"],
                    new_decision_ids=decision_ids,
                    new_outcome_stats=merged,
                    new_lesson=retro.get("lesson"),
                    new_applicable_when=retro.get("applicable_when"),
                    new_caveats=retro.get("caveats"),
                )
            else:
                create_experience(
                    self.db_path, tags=tags,
                    scenario_summary=retro.get("scenario_summary", ""),
                    decisions_referenced=decision_ids,
                    outcome_stats=outcome,
                    lesson=retro.get("lesson", ""),
                    applicable_when=retro.get("applicable_when", ""),
                    caveats=retro.get("caveats", ""),
                )
        print(f"[retro] processed {len(groups)} tag groups, {len(closed)} decisions")
```

- [ ] **Step 2: Commit**

```bash
git add agent_system/runners/retrospective_runner.py
git commit -m "feat: retrospective_runner 每日复盘 → 经验聚合"
```

---

### Task 4.4: 在 start.py 接入状态追踪 + 复盘调度

**Files:**
- Modify: `agent_system/start.py`

- [ ] **Step 1: 在 `start.py` 顶部 import 区追加**

```python
from agent_system.runners.decision_status_tracker import DecisionStatusTracker
from agent_system.runners.retrospective_runner import RetrospectiveRunner
```

- [ ] **Step 2: 在 main() 中实例化追踪器和复盘 + 启动两条循环**

在原有的 `_scan_loop` / `_tracking_loop` 启动之后追加：

```python
    # 决策状态追踪器: 每 1 小时
    status_tracker = DecisionStatusTracker(db_path=db_path, binance=binance, expire_days=7)
    def _status_loop():
        while not _stop_flag.is_set():
            try:
                status_tracker.run_once()
            except Exception as e:
                print(f"[status_loop] {e}")
            _stop_flag.wait(3600)
    threading.Thread(target=_status_loop, daemon=True).start()

    # 每日凌晨复盘 (cron 解析简化为: 检查当前时间, 凌晨 3:00-3:10 之间触发, 一天最多触发一次)
    retro_runner = RetrospectiveRunner(cfg=cfg, llm_client=llm, db_path=db_path)
    last_retro_date = [None]
    def _retro_loop():
        from datetime import datetime as dt
        while not _stop_flag.is_set():
            now = dt.now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == 3 and last_retro_date[0] != today:
                try:
                    retro_runner.run_daily()
                    last_retro_date[0] = today
                except Exception as e:
                    print(f"[retro_loop] {e}")
            _stop_flag.wait(600)  # 每 10 分钟检查一次
    threading.Thread(target=_retro_loop, daemon=True).start()
```

- [ ] **Step 3: 端到端验证**

启动 `python -m agent_system.start`，做几次对话产出决策。
等价地手动触发：

```bash
python -c "
from agent_system.core.config_loader import load_config
from agent_system.data.binance_client import BinanceClient
from agent_system.runners.decision_status_tracker import DecisionStatusTracker
import os
cfg = load_config('agent_system/config.yaml')
b = BinanceClient(api_key=os.environ.get('BINANCE_API_KEY'), api_secret=os.environ.get('BINANCE_API_SECRET'))
DecisionStatusTracker(db_path=cfg['data_db'], binance=b).run_once()
print('OK')
"
```

Expected: 输出 `OK`，open 决策按价格变化更新状态。

- [ ] **Step 4: Commit**

```bash
git add agent_system/start.py
git commit -m "feat: start.py 接入状态追踪(每1h) + 每日复盘(凌晨3点)"
```

---

### Task 4.5: experience Mate 接入 orchestrator（仍 enabled=false）

**Files:**
- Modify: `agent_system/mates/experience.py`
- Modify: `agent_system/core/orchestrator.py`

- [ ] **Step 1: 实现 `mates/experience.py` 的检索逻辑**

```python
from agent_system.mates.base import BaseMate
from agent_system.data.experience_store import search_by_tags

class ExperienceMate(BaseMate):
    def __init__(self, *args, db_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = db_path

    def run(self, data_pack, extra_ctx=None, audit_logger=None, audit_id=None, round_num=1):
        tags = data_pack.get("tags", [])
        retrieved = search_by_tags(self.db_path, query_tags=tags, limit=5, days=90) if self.db_path else []
        merged_extra = dict(extra_ctx or {})
        merged_extra["retrieved_experiences_json"] = retrieved
        if not retrieved:
            return {"mate": "experience", "view": "观望", "confidence": 0,
                    "evidence": ["经验库尚未有匹配场景"], "extra": {"similar_cases": []}}
        return super().run(data_pack, extra_ctx=merged_extra,
                            audit_logger=audit_logger, audit_id=audit_id, round_num=round_num)
```

- [ ] **Step 2: 在 `cli/__main__.py` 与 `start.py` 实例化 experience Mate 时传 db_path**

修改 `_register_mate_classes()` / `_build_orchestrator()` 内 ExperienceMate 实例化，特殊处理：

```python
from agent_system.mates.experience import ExperienceMate
# ... 实例化每个 mate 的循环里:
if name == "experience":
    instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg,
                    prompts_dir=prompts_dir, db_path=cfg["data_db"])
else:
    instance = cls(name=name, llm_client=llm, mate_cfg=mate_cfg, prompts_dir=prompts_dir)
```

把这段加到 `cli/__main__.py` 的 `_build_orchestrator()` 与 `start.py` 的 `_build_orchestrator()` 里同样位置。

- [ ] **Step 3: Commit**

```bash
git add agent_system/mates/experience.py agent_system/cli/__main__.py agent_system/start.py
git commit -m "feat: experience Mate 接入(检索经验库, 仍 enabled=false)"
```

---

### Task 4.6: CLI retrospective 手动触发

**Files:**
- Modify: `agent_system/cli/__main__.py`

- [ ] **Step 1: 在 CLI 增加 `retrospective` 子命令**

```python
def cmd_retro(args):
    cfg = load_config(args.config)
    llm = _build_llm_client(cfg)
    from agent_system.runners.retrospective_runner import RetrospectiveRunner
    runner = RetrospectiveRunner(cfg=cfg, llm_client=llm, db_path=cfg["data_db"])
    runner.run_daily()
    print("done")

# 在 main() 的 sub.add_parser 部分追加:
p_retro = sub.add_parser("retrospective")
p_retro.add_argument("--config", default="agent_system/config.yaml")
p_retro.set_defaults(func=cmd_retro)
```

- [ ] **Step 2: 验证**

Run: `python -m agent_system.cli retrospective`
Expected: 输出 `[retro] processed N tag groups, M decisions` 或 `[retro] no closed decisions in last 24h`

- [ ] **Step 3: Commit**

```bash
git add agent_system/cli/__main__.py
git commit -m "feat: CLI retrospective 手动触发复盘"
```

---

## Phase 5 — 启用经验 Mate + 调优（持续）

**目标**：经验数据积累足够后启用 experience Mate，监控效果，持续调优。

### Task 5.1: 监控 experience 命中率

**Files:**
- Modify: `agent_system/mates/experience.py`
- Modify: `agent_system/core/orchestrator.py`

- [ ] **Step 1: ExperienceMate 在结果中标注 `_hit_count`**

替换 `mates/experience.py` 中的 `run` 方法：

```python
def run(self, data_pack, extra_ctx=None, audit_logger=None, audit_id=None, round_num=1):
    tags = data_pack.get("tags", [])
    retrieved = search_by_tags(self.db_path, query_tags=tags, limit=5, days=90) if self.db_path else []
    if not retrieved:
        return {"mate": "experience", "view": "观望", "confidence": 0,
                "evidence": ["经验库尚未有匹配场景"],
                "extra": {"similar_cases": [], "_hit_count": 0}}
    merged_extra = dict(extra_ctx or {})
    merged_extra["retrieved_experiences_json"] = retrieved
    result = super().run(data_pack, extra_ctx=merged_extra,
                          audit_logger=audit_logger, audit_id=audit_id, round_num=round_num)
    if "extra" not in result or not isinstance(result.get("extra"), dict):
        result["extra"] = {}
    result["extra"]["_hit_count"] = len(retrieved)
    return result
```

- [ ] **Step 2: orchestrator 在保存决策时把 `_hit_count` 也存到 card_json**

不需要改 orchestrator 本身，因为 experience Mate 的输出已经在 round_1_reports 中传给 decision_lead，并最终通过 audit_logger 落盘。card_json 已包含。

- [ ] **Step 3: Commit**

```bash
git add agent_system/mates/experience.py
git commit -m "feat: experience Mate 输出含 _hit_count, 用于命中率监控"
```

---

### Task 5.2: 启用 experience Mate 的检查脚本

**Files:**
- Create: `agent_system/cli/check_ready.py`

- [ ] **Step 1: 实现 `cli/check_ready.py`**

```python
import sys
from agent_system.core.config_loader import load_config
from agent_system.data.db import get_conn

def main():
    cfg = load_config("agent_system/config.yaml")
    db = cfg["data_db"]
    conn = get_conn(db)
    n_exp = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
    n_dec = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    n_closed = conn.execute("SELECT COUNT(*) FROM decisions WHERE status IN ('win','loss','expired')").fetchone()[0]
    conn.close()

    print(f"experiences: {n_exp}")
    print(f"decisions total: {n_dec}, closed: {n_closed}")

    enabled = cfg.get("mates", {}).get("experience", {}).get("enabled")
    if n_exp >= 30:
        if enabled:
            print("✓ experience Mate 已启用,经验库充足")
        else:
            print("⚠ 经验库已 ≥ 30 条,但 mates.experience.enabled 仍为 false")
            print("  请改为 true 后重启 start.py")
            sys.exit(1)
    else:
        print(f"经验库不足 30 条({n_exp}),请继续记录,暂不启用 experience Mate")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证**

Run: `python -m agent_system.cli.check_ready`
Expected: 当前 experiences 表为空时输出"经验库不足 30 条"

- [ ] **Step 3: Commit**

```bash
git add agent_system/cli/check_ready.py
git commit -m "feat: CLI check_ready 检查是否可启用 experience Mate"
```

---

### Task 5.3: README 文档

**Files:**
- Create: `agent_system/README.md`

- [ ] **Step 1: 创建 README**

```markdown
# Agent Team 量化分析系统

币安 U 本位永续合约智能体分析系统(11 Mate 圆桌辩论 + 轻量经验复盘)。

详细设计见 `docs/superpowers/specs/2026-05-16-agent-team-design.md`。
实现路线见 `docs/superpowers/plans/2026-05-16-agent-team-system.md`。

## 快速开始

### 1. 配置环境变量

```bash
export DEEPSEEK_API_KEY=sk-xxx
export BINANCE_API_KEY=xxx
export BINANCE_API_SECRET=xxx
export SERVER_CHAN_KEY=SCT-xxx   # 可选, 不设则不推送
```

### 2. 安装依赖

```bash
pip install -r agent_system/requirements.txt
```

### 3. 一键启动

```bash
python -m agent_system.start
```

打开 http://localhost:5000

### 4. 命令行调试

```bash
# 跑单个 Mate
python -m agent_system.cli dry_run --symbol ETHUSDT --mate trend_multi_tf

# 跑完整 11 Mate 三轮辩论
python -m agent_system.cli dry_run --symbol ETHUSDT --mode full

# 切换模型
python -m agent_system.cli dry_run --symbol ETHUSDT --mate red_team --model deepseek-reasoner

# 手动触发复盘
python -m agent_system.cli retrospective

# 检查能否启用 experience Mate
python -m agent_system.cli.check_ready
```

## 项目结构

参见 `docs/superpowers/plans/2026-05-16-agent-team-system.md` 中"文件结构"小节。

## 启用 experience Mate

1. 系统跑满 30 天,生成 ≥ 30 条经验
2. 运行 `python -m agent_system.cli.check_ready` 验证
3. 修改 `agent_system/config.yaml`: `mates.experience.enabled: true`
4. 重启 `python -m agent_system.start`
```

- [ ] **Step 2: Commit**

```bash
git add agent_system/README.md
git commit -m "docs: README 快速开始 + 命令行用法"
```

---

## 验收清单（每个 Phase 都要过）

每个 Phase 完成都跑一次：

```bash
# 单元测试
pytest agent_system/tests/ -v --ignore=agent_system/tests/integration

# 集成测试
pytest agent_system/tests/integration/ -v

# 端到端 dry run (Phase 1+ 都要能跑)
python -m agent_system.cli dry_run --symbol ETHUSDT --mate trend_multi_tf

# Phase 2+ 还要能跑完整模式
python -m agent_system.cli dry_run --symbol ETHUSDT --mode full

# Phase 3+ 还要能启动 web 服务
python -m agent_system.start
# 浏览器访问 http://localhost:5000 测对话
```

预期产物：
- 全部测试 PASS
- `tracks/` 下有审计 JSON 文件,结构完整
- `funding_rate.db` 中 `decisions` 表有数据(Phase 3+)
- `experiences` 表有数据(Phase 4+ 复盘后)
