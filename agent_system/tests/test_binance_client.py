from unittest.mock import MagicMock
import pytest
import requests
from agent_system.data.binance_client import BinanceClient, build_signature


def _fake_response(json_value, status=200):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=json_value)
    r.status_code = status
    return r


def test_build_signature_deterministic():
    sig1 = build_signature(secret="abc", query_string="symbol=BTCUSDT&timestamp=1")
    sig2 = build_signature(secret="abc", query_string="symbol=BTCUSDT&timestamp=1")
    assert sig1 == sig2
    assert len(sig1) == 64


def test_get_klines_builds_url():
    captured = {}
    client = BinanceClient(api_key="k", api_secret="s")

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        return _fake_response([[1, "1", "2", "3", "4", "5", 6, "7", 8, "9", "10", "11"]])

    client._session.get = fake_get
    out = client.get_klines("BTCUSDT", interval="1h", limit=10)
    assert "/fapi/v1/klines" in captured["url"]
    assert captured["params"]["symbol"] == "BTCUSDT"
    assert captured["params"]["interval"] == "1h"
    assert captured["params"]["limit"] == 10
    assert len(out) == 1


def test_get_funding_info_uses_get():
    captured = {}
    client = BinanceClient(api_key="k", api_secret="s")

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        return _fake_response([{"symbol": "BTCUSDT"}])

    client._session.get = fake_get
    out = client.get_funding_info()
    assert "/fapi/v1/fundingInfo" in captured["url"]
    assert isinstance(out, list)


def test_headers_includes_api_key():
    client = BinanceClient(api_key="my-key")
    assert client._headers().get("X-MBX-APIKEY") == "my-key"


def test_headers_empty_without_api_key():
    client = BinanceClient()
    assert "X-MBX-APIKEY" not in client._headers()


def test_get_retries_on_connection_reset_then_succeeds(monkeypatch):
    """ConnectionError 应触发应用层重试,第二次成功后返回正确数据。"""
    client = BinanceClient()
    monkeypatch.setattr(client, "APP_RETRY_BACKOFF", 0)  # 测试不要真的 sleep

    calls = {"n": 0}
    def flaky_get(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ConnectionError("RST")
        return _fake_response([{"symbol": "BTCUSDT"}])

    client._session.get = flaky_get
    out = client.get_funding_info()
    assert calls["n"] == 2
    assert out == [{"symbol": "BTCUSDT"}]


def test_get_gives_up_after_max_retries(monkeypatch):
    """连续 ConnectionError 超过重试次数后, 异常向上抛。"""
    client = BinanceClient()
    monkeypatch.setattr(client, "APP_RETRY_BACKOFF", 0)
    calls = {"n": 0}
    def always_fail(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        raise requests.exceptions.ConnectionError("RST")

    client._session.get = always_fail
    with pytest.raises(requests.exceptions.ConnectionError):
        client.get_funding_info()
    assert calls["n"] == client.APP_RETRY_MAX
