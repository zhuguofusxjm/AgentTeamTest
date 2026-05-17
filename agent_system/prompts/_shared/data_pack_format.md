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
