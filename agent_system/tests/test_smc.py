"""测试 SMC 计算核心。

参数全部用小尺寸 (swing=3, atr=5 等),让测试 K 线序列短一些,易看清。
"""

from agent_system.core.smc import compute_smc, BULLISH, BEARISH


def _bar(t, o, c, h=None, l=None):
    return {
        "open_time": t,
        "open": o,
        "close": c,
        "high": h if h is not None else max(o, c),
        "low": l if l is not None else min(o, c),
        "volume": 1,
        "quote_volume": 1,
        "taker_buy_volume": 0.5,
        "taker_buy_quote_volume": 0.5,
    }


def _flat_bars(n, base=100, t0=0):
    return [_bar(t0 + i, base, base, base + 0.5, base - 0.5) for i in range(n)]


def test_insufficient_data_returns_status():
    klines = _flat_bars(5)
    out = compute_smc(klines, swing_length=50, atr_period=200)
    assert out["_status"] == "insufficient_data"
    assert out["n_bars"] == 5


def test_basic_compute_returns_ok_with_enough_bars():
    klines = _flat_bars(20)
    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    assert out["_status"] == "ok"
    assert out["n_bars"] == 20
    assert out["current_price"] == 100
    assert "swing" in out
    assert "fvg" in out
    assert "order_blocks" in out
    assert "zone" in out


def test_zone_premium_when_price_near_top():
    """构造 trailing 区间 [100, 110],让最后 close 接近顶 → premium."""
    bars = []
    for i in range(15):
        bars.append(_bar(i, 105, 105, 110 if i == 0 else 105.5,
                         100 if i == 0 else 104.5))
    bars[-1] = _bar(14, 109, 109, 109.5, 108.5)
    out = compute_smc(bars, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    assert out["zone"] == "premium"


def test_zone_discount_when_price_near_bottom():
    """构造 trailing 区间 [100, 110],让最后 close 接近底 → discount."""
    bars = []
    for i in range(15):
        bars.append(_bar(i, 105, 105, 110 if i == 0 else 105.5,
                         100 if i == 0 else 104.5))
    bars[-1] = _bar(14, 101, 101, 101.5, 100.5)
    out = compute_smc(bars, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    assert out["zone"] == "discount"


def test_bullish_bos_detected():
    """构造连续两次破前高: 先破 → CHoCH (从 0 转 bullish),再破 → BOS."""
    closes = [10, 12, 15, 14, 12, 10,    # swing high = 15
              16, 17, 18,                  # 破 15, bullish (CHoCH/BOS, 因 prev_bias=0 → BOS)
              17, 16, 15, 14,              # 回调形成新 swing high = 18
              19, 20, 21, 21, 21]          # 再破, 此时为 bullish BOS (prev=BULLISH → BOS)
    klines = []
    for i, c in enumerate(closes):
        klines.append(_bar(i, c, c, c + 0.5, c - 0.5))
    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    assert out["_status"] == "ok"
    assert out["swing"]["trend_bias"] == "bullish"
    last = out["swing"]["last_event"]
    assert last is not None
    assert last["type"] == "BOS"
    assert last["side"] == "bullish"


def test_choch_after_bullish_then_bearish_break():
    """先 bullish BOS,然后跌破前 swing low → bearish CHoCH."""
    closes = [10, 12, 15, 14, 12, 8, 10, 12, 14, 16,  # 制造 bullish BOS
              14, 12, 10, 8, 6, 5, 5, 5]               # 跌破 swing low (7.5)
    klines = []
    for i, c in enumerate(closes):
        klines.append(_bar(i, c, c, c + 0.5, c - 0.5))
    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    assert out["_status"] == "ok"
    assert out["swing"]["trend_bias"] == "bearish"
    last = out["swing"]["last_event"]
    assert last["type"] == "CHoCH"
    assert last["side"] == "bearish"


def test_fvg_detected_then_filled():
    """构造 bullish FVG,然后让价格回填 → FVG 列表为空."""
    klines = []
    for i in range(5):
        klines.append(_bar(i, 100, 100, 100.5, 99.5))
    klines.append(_bar(5, 100, 120, 121, 99))      # 强阳线 bar
    klines.append(_bar(6, 120, 120, 121, 110))     # bar.low=110 > bar[4].high=100.5 → FVG
    klines.append(_bar(7, 120, 95, 121, 85))       # low=85 < 100.5 → 失效

    for _ in range(8):
        klines.append(_bar(len(klines), 95, 95, 95.5, 94.5))

    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    bullish_fvgs = [f for f in out["fvg"] if f["bias"] == "bullish"]
    assert bullish_fvgs == []


def test_fvg_persists_when_not_filled():
    """bullish FVG 形成后价格不回填 → FVG 仍在列表中."""
    klines = []
    for i in range(5):
        klines.append(_bar(i, 100, 100, 100.5, 99.5))
    klines.append(_bar(5, 100, 120, 121, 99))
    klines.append(_bar(6, 120, 120, 121, 110))     # FVG 产生
    for i in range(7, 16):
        klines.append(_bar(i, 120, 121, 122, 110))  # 一直在 FVG 上方

    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    bullish_fvgs = [f for f in out["fvg"] if f["bias"] == "bullish"]
    assert len(bullish_fvgs) >= 1


def test_ob_max_limit():
    """OB 数量不会超过 ob_max."""
    klines = _flat_bars(60)
    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5, ob_max=3)
    assert len(out["order_blocks"]["swing"]) <= 3
    assert len(out["order_blocks"]["internal"]) <= 3


def test_output_shape_complete():
    """输出包含所有约定字段."""
    klines = _flat_bars(30)
    out = compute_smc(klines, swing_length=3, internal_length=2,
                      eqhl_length=2, atr_period=5)
    expected_keys = {"_status", "n_bars", "current_price", "atr",
                     "swing", "internal", "order_blocks", "fvg",
                     "equal_highs", "equal_lows", "zone", "zone_levels"}
    assert expected_keys.issubset(out.keys())
    assert "trend_bias" in out["swing"]
    assert "swing" in out["order_blocks"]
    assert "internal" in out["order_blocks"]
    assert {"trailing_top", "trailing_bottom", "premium_threshold",
            "discount_threshold", "equilibrium_low", "equilibrium_high"} <= out["zone_levels"].keys()
