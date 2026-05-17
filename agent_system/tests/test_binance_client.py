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
