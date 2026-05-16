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

def test_retry_on_exception(monkeypatch):
    monkeypatch.setattr("agent_system.core.llm_client.time.sleep", lambda x: None)
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
