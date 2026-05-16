# 币安 U 本位合约智能体分析系统 — 重构设计文档

> 创建日期：2026-05-16
> 替换对象：旧"信号引擎 + DeepSeek 二次诊断"系统
> 设计模式：Agent Team Roundtable 辩论 + 轻量经验复盘

---

## 一、设计目标与背景

### 1.1 旧系统的不足

旧系统采用"定时执行 + 固定指标打分 + LLM 二次诊断"模式，存在两大问题：

1. **缺少多周期综合分析** — 单一时间窗口的指标快照，无法兼顾 1h 短线、4h 中线、1d/1w 趋势的协同判断
2. **可扩展性差** — 加新信号要改 signals.py 评分逻辑、改回测、改前端展示，耦合度高

### 1.2 新系统的核心理念

把"打分 + 单次 LLM 诊断"重构为**多 Agent 圆桌辩论**：

- 用户用自然语言提问（"帮我分析 ETH 是否有买卖点"）
- 系统派出 11 个专精 Mate 并行分析
- 经过 3 轮辩论（独立分析 → 蒋军反驳 → Lead 综合）
- 输出决策卡片（方向、入场价、止损止盈、可信度、依据、风险）
- 每次决策入库，定期复盘沉淀经验，下轮决策由经验 Mate 检索复用

### 1.3 设计选型小结

| # | 维度 | 决定 |
|---|------|------|
| 1 | 触发模式 | 对话 + 定时扫描 + 持仓跟踪 三模式 |
| 2 | 协调架构 | Roundtable 辩论式 |
| 3 | Teammate 角色 | 11 个分析师（保留扩展性） |
| 4 | 复盘机制 | 轻量：记录 + 检索（不引入向量库） |
| 5 | Agent 框架 | 原生 API 自研（不依赖 LangGraph 等） |
| 6 | LLM 选型 | 抽象层 + 可配置；第一阶段 DeepSeek 单家 |
| 7 | 用户入口 | 全新对话主页（三栏布局） |
| 8 | 兼容方式 | 全新项目目录 + 复用现有 SQLite |
| 9 | 辩论节奏 | 固定 3 轮 |
| 10 | 输出 | 决策卡片紧凑式 |

---

## 二、系统总体架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                              用户层                                    │
│   全新对话主页 (chat.html):  左侧扫描+跟踪 | 中间对话 | 右侧辩论流       │
│   微信推送 (Server酱)        :  决策卡片 + 关键节点                     │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────┐
│                           应用接入层                                   │
│   web/app.py (Flask)    : Web路由 + 对话API + SSE流式推送              │
│   start.py              : 一键启动 web + 三 runner                     │
│   runners/              : chat / scan / tracking / retrospective       │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────┐
│                        Agent Team 编排层                              │
│   ┌──────────────────────────────────────────────────────────┐        │
│   │  core/orchestrator.py — Lead 调度器                       │        │
│   │  - parse_query (理解用户意图)                              │        │
│   │  - data_packer.build (一次性聚合数据包)                    │        │
│   │  - run_round_1: 11 Mate 并行独立分析(分两批)               │        │
│   │  - run_round_2: 蒋军反驳 + 被点名 Mate 回应                │        │
│   │  - run_round_3: Lead 综合 → 决策卡片                       │        │
│   │  - audit_logger (全程 LLM 审计落盘)                        │        │
│   └──────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────┐
│                          Teammate 层 (11个)                           │
│  trend_multi_tf  funding_rate    smart_money    long_short_compare    │
│  volatility      experience      red_team       macro_sentiment       │
│  liquidity       position_mgr    decision_lead(系统级,被Lead直调)     │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────┐
│                       LLM 抽象层 (core/llm_client.py)                 │
│   统一接口: chat(model, messages, ...) → text + token usage           │
│   provider: deepseek (第一阶段) / claude / openai (预留)              │
│   每个 Mate 在 config.yaml 中绑定自己的 model                          │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────┐
│                           数据访问层                                   │
│   data/data_packer.py    : 聚合 K线/费率/持仓/多空比/ATR/布林          │
│   data/binance_client.py : 币安签名版 (用 API_KEY/SECRET 提高限额)     │
│   data/experience_store.py: 经验库 CRUD + 标签检索                     │
│   data/decisions_store.py : 决策快照 CRUD + 状态追踪                   │
│   data/db.py (复用旧表)   : 现有 SQLite 表 + 新增 3 张表               │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
┌──────────────────────────────────────┴───────────────────────────────┐
│                              数据层                                    │
│   funding_rate.db (复用)  +  新增表:                                  │
│     - decisions          : 每次决策快照 + 状态(open/win/loss/expired) │
│     - experiences        : 复盘后沉淀的经验文本 + 标签                 │
│     - chat_messages      : 对话历史                                    │
│   tracks/ (复用 + 扩展)   : 增加 chat_*.json / decision_*.json         │
└──────────────────────────────────────────────────────────────────────┘
```

**关键约定：**
- 全新项目目录 `agent_system/`，与旧文件并列
- 复用 `funding_rate.db`，只新增表，不改既有表
- 数据采集（fetch_*.py）继续沿用，不改造
- 旧的 signals.py 复用为"预筛子"（扫描场景下做候选筛选）
- 旧的 monitor.py / app.py / start.py / 旧前端 — 不再使用，但不删除

---

## 三、Teammate 契约

每个 Mate 的契约统一格式：**输入 → 关注维度 → 输出 schema**。

### 3.1 共享输入：DataPack

辩论开始前由 Lead 调用 `data_packer.build(symbol)` 一次生成，所有 Mate 共享：

```yaml
symbol: ETHUSDT
timestamp: 2026-05-16 14:30
price_now: 3128.5
klines:
  1h:  [近 168 根]   # 7天
  4h:  [近 180 根]   # 30天
  1d:  [近 180 根]   # 半年
  1w:  [近 104 根]   # 2年
funding:
  current: 0.0089%
  history_30d: [...]
  cap, floor, interval_hours
positions:
  oi_history: [...]            # 持仓量
  top_position_ratio: [...]    # 大户持仓比
  top_account_ratio: [...]     # 大户账户比
  global_account_ratio: [...]  # 全市场多空比
volume:
  recent_24h, ma_7d
  taker_buy_ratio_recent
indicators:    # 预算好的
  atr_12h, atr_7d
  bb_width_now, bb_width_pct
  ema_20/50/200 各周期
peer_funding:  # 跨币种
  btc, sol, ... 当前费率
```

### 3.2 11 个 Mate 的职责

**1. 多周期趋势分析师 (trend_multi_tf)**
- 关注：1h/4h/1d/1w 趋势方向、均线排列、MACD 背离
- 输出：`{view, confidence, evidence, cycle_summary: {1h, 4h, 1d, 1w}}`

**2. 资金费率分析师 (funding_rate)**
- 关注：费率绝对值是否极端、近期趋势、跨币种对比
- 输出：`{view, confidence, evidence, risk_flag: 拥挤/正常}`

**3. 聪明钱分析师 (smart_money)**
- 关注：大户持仓比、大户账户比变化、持仓量增减、主买主卖
- 输出：`{view, confidence, evidence, smart_money_direction}`

**4. 多空对比分析师 (long_short_compare)**
- 关注：全市场多空比 vs 大户多空比的背离方向和幅度
- 输出：`{view, confidence, evidence, divergence_score: 0-100}`

**5. 波动压缩分析师 (volatility)**
- 关注：ATR 12h/7d 比值、布林带带宽分位、价格收敛形态
- 输出：`{view, confidence, evidence, breakout_imminent: bool}`

**6. 经验复盘分析师 (experience)**
- 关注：检索经验库，找出当前场景标签的历史经验
- 输出：`{view, confidence, evidence, similar_cases: [{tags, outcome, lesson}]}`
- **冷启动期 enabled=false**

**7. 蒋军风险分析师 (red_team)**
- 第 1 轮独立判断时：列出当前布局下最可能让人亏钱的 3 条主要风险路径
- 第 2 轮反驳时：针对多数派观点逐条反驳
- 输出：`{counterview, risks, black_swan_scenarios}`

**8. 宏观情绪分析师 (macro_sentiment)**
- 关注：BTC 主导率、整体加密市场情绪、相关币联动
- 输出：`{view, confidence, evidence, market_regime: 牛/熊/震荡}`

**9. 流动性/订单簿分析师 (liquidity)**
- 关注：盘口深度、大单流向（第一阶段用持仓量+成交量+主买主卖近似）
- 输出：`{view, confidence, evidence, liquidity_health: 好/一般/差}`

**10. 仓位管理师 (position_mgr)**
- 关注：基于其他 Mate 输出，给出止损/止盈/仓位大小建议
- **第 1 轮内分两批**：其他 10 个 Mate 完成后才执行
- 输出：`{stop_loss, take_profit, position_size_pct, risk_reward_ratio}`

**11. 决策 Lead (decision_lead, 系统级)**
- 不参与并行调度，是 Orchestrator 的角色
- 第 3 轮综合所有 Mate 输出 + 蒋军反驳 → 输出最终决策卡片

### 3.3 输出统一 schema

每个 Mate 都返回 JSON：

```json
{
  "mate": "trend_multi_tf",
  "view": "多",
  "confidence": 72,
  "evidence": [
    "4h MACD 金叉且柱状放大",
    "1d 均线多头排列（EMA20 > EMA50 > EMA200）",
    "1w 处于上升通道下沿"
  ],
  "concerns": ["1h 出现顶背离，短期回撤风险"],
  "extra": { "cycle_summary": {...} }
}
```

### 3.4 扩展性约定

新增 Mate 只需 3 步：
1. 写 prompt 模板（`prompts/<mate>.md`）
2. 在 `config.yaml` 注册名称、绑定模型、设置启用
3. Lead 调度循环自动包含

DataPack 字段是**叠加式**，新增字段对老 Mate 无影响。

---

## 四、圆桌辩论 3 轮流程

```
用户问题: "帮我分析 ETH 合约是否有合适的买卖点，并给出计划"
                            │
                            ▼
            Lead.parse_query → {symbol, intent}
                            │
                            ▼
            data_packer.build(symbol) → DataPack
                            │
                            ▼
╔══════════════════════════ 第 1 轮 ══════════════════════════╗
║                  独立分析（并行）                            ║
║                                                              ║
║  Batch 1 (并行 9 个):                                        ║
║   trend_multi_tf  funding_rate  smart_money                  ║
║   long_short_compare  volatility  experience                 ║
║   red_team(列风险) macro_sentiment liquidity                 ║
║                                                              ║
║  Batch 2 (依赖 Batch 1 输出):                                ║
║   position_mgr (基于其他 Mate 共识算止损止盈仓位)            ║
║                                                              ║
║  → 产物: round_1_reports                                     ║
╚══════════════════════════════════════════════════════════════╝
                            │
                            ▼
╔══════════════════════════ 第 2 轮 ══════════════════════════╗
║                  蒋军反驳 + Mate 回应                       ║
║                                                              ║
║  Step 2.1  Lead 统计第 1 轮 view 分布 → majority             ║
║  Step 2.2  red_team 接收 round_1_reports + majority,         ║
║            逐条反驳 + 列风险路径                             ║
║  Step 2.3  挑出被点名的 Mate (top 3 confidence 多数派),      ║
║            并行让它们回应蒋军                                ║
║                                                              ║
║  → 产物: round_2_debate = {rebuttal, responses}              ║
╚══════════════════════════════════════════════════════════════╝
                            │
                            ▼
╔══════════════════════════ 第 3 轮 ══════════════════════════╗
║                  Lead 综合 → 决策卡片                        ║
║                                                              ║
║  Lead 拿到全部材料(DataPack 摘要 + round_1 + round_2)        ║
║  Prompt: "综合所有信息, 给出最终决策卡片"                    ║
║                                                              ║
║  → 产物: decision_card (JSON)                                ║
╚══════════════════════════════════════════════════════════════╝
                            │
                            ▼
            落盘 + 推送:
              - decisions 表 (DB)
              - tracks/decision_<id>.json (审计)
              - SSE 推送到前端
              - 微信推送 (Server酱)
```

### 4.1 决策卡片 JSON

```json
{
  "decision_id": 42,
  "symbol": "ETHUSDT",
  "timestamp": "2026-05-16 14:30:15",
  "direction": "多",
  "entry_price": 3120,
  "entry_zone": [3110, 3135],
  "stop_loss": 3050,
  "take_profit": 3260,
  "risk_reward_ratio": 2.0,
  "position_size_pct": 15,
  "confidence": 68,
  "key_evidence": [
    "4h MACD 金叉 + 1d 均线多头排列 (trend)",
    "大户持仓比 2.1，多头主导 (smart_money)",
    "全市场多空比偏空但大户偏多，散户被收割概率高 (long_short)"
  ],
  "key_risks": [
    "费率 0.012%，多头略拥挤，反转踩踏风险 (red_team)",
    "1h 顶背离信号，短期可能先回撤至 3100 (trend)",
    "BTC 在阻力位附近，若回落 ETH 难独立 (macro)"
  ],
  "execution_plan": "在 3110-3135 分批进场 50%+50%，跌破 3050 止损，目标 3260；如 BTC 跌破 65000 立即减仓"
}
```

### 4.2 Token 与延迟预估

> 以下基于 `full` 模式所有 Mate 都启用估算。冷启动期 experience Mate 关闭时，第 1 轮 Batch 1 减少 1 次调用。

| 阶段 | LLM 调用次数 | 预估延迟 |
|------|-------------|---------|
| 第 1 轮 Batch 1 | 9 次（并行） | ~8s（受最慢 Mate 限制） |
| 第 1 轮 Batch 2 | 1 次 | ~3s |
| 第 2 轮 | 1 + 3 次（反驳后并行回应） | ~6s |
| 第 3 轮 | 1 次 | ~5s |
| **总计** | **15 次 LLM 调用** | **~22 秒** |

### 4.3 异常与降级

- 任意 Mate 超时（>30s）或返回非法 JSON：跳过，记入审计日志，Lead 在第 3 轮 prompt 里说明"X Mate 缺席"
- 全部 Mate 都失败：返回错误，不出决策（避免误导）
- LLM 限流：以 Mate 为粒度退避重试，最多 2 次

---

## 五、三种触发模式

### 5.1 模式一：用户对话（主入口）

```
用户在 chat.html 输入: "帮我分析 ETH 是否有买卖点"
        │
        ▼
chat_runner.handle_message(text):
  - 解析意图（单币分析 / 多币对比 / 跟踪问询 / 闲聊）
  - single_analysis → orchestrator.run(symbol, mode='full')
  - tracking_query → 直接读 tracks/ 数据
  - data_query → 直接查 DB
  - chitchat → LLM 直接回复
        │
        ▼
SSE 流式推送:
  右侧实时展示辩论流（每个 Mate 完成时推送一帧）
  中间对话区最终展示决策卡片
        │
        ▼
保存到 chat_messages 表
```

意图解析由 Lead 的轻量 prompt 完成（不走完整 11 Mate），返回结构化字段：

```json
{ "intent": "single_analysis", "symbol": "ETHUSDT", "extra": {} }
```

### 5.2 模式二：定时扫描

```
monitor 每 30 分钟触发
        │
        ▼
scan_runner.run():
  Step 1  扫描全市场，复用旧 signals.py 做预筛(规则引擎,便宜快速)
          → 候选 N 个币种(默认 10,可在 config 调)
        │
        ▼
  Step 2  对每个候选币种串行调 orchestrator.run(symbol, mode='lean')
          → 11 Mate 简化 2 轮辩论
        │
        ▼
  Step 3  按 confidence 排序,取 top 3-5
        │
        ▼
  Step 4  推送微信 + 写入 decisions 表
```

**关键设计：保留旧 signals.py 作为预筛子。**
- 旧的 12 信号评分逻辑很快、很便宜，作为"漏斗"
- Agent Team 只对预筛通过的币种深度分析
- 全市场 600+ 币种 → 每轮只跑 ~10 次完整 Team

### 5.3 模式三：持仓跟踪

```
monitor 每 15 分钟触发
        │
        ▼
tracking_runner.run():
  获取所有 status=active 的跟踪
        │
        ▼
  对每个跟踪 (symbol + entry):
    - data_packer.build(symbol)
    - 注入 跟踪上下文(entry_price, direction, pnl, 历史 5 次分析)
    - orchestrator.run(symbol, mode='tracking')
        │
        ▼
  跟踪模式下 Mate 调度调整:
    - 启用: trend_multi_tf, funding_rate, smart_money,
            long_short_compare, red_team, position_mgr, experience
    - 禁用: macro_sentiment, liquidity, volatility (跟踪场景价值低)
    - 第 3 轮决策卡片格式改为跟踪建议:
      { action: 持有/加仓/减仓/平仓, reasoning, urgency: 立即/可观察/不急 }
        │
        ▼
  推送 + 落盘 (沿用旧 tracks/<symbol>_<id>.json 格式扩展)
```

### 5.4 三种"模式档位"统一抽象

| 档位 | 启用 Mate | 辩论轮数 | 用于 |
|------|----------|---------|------|
| `full` | 全部 11 个 | 3 轮 | 用户对话单币深度分析 |
| `lean` | 7 个核心 | 2 轮（去掉第 2 轮蒋军反驳） | 定时扫描批量分析 |
| `tracking` | 7 个跟踪相关 | 2 轮 | 持仓跟踪 |

每个档位在 `config.yaml` 里配置 Mate 启用列表 + 轮数 + 输出 schema。
`orchestrator.run(symbol, mode='full'|'lean'|'tracking')` 是统一入口。

**启用优先级规则**：实际是否启用某 Mate = `mates.<mate>.enabled` AND `mates.<mate>` 在当前 mode 的 `enabled_mates` 列表中。
任一条件为 false 则跳过该 Mate。这意味着冷启动期把 `mates.experience.enabled = false` 即可全模式禁用经验 Mate，无需逐个 mode 删除。

### 5.5 调度与并发控制

| 场景 | 并发策略 | 单次耗时 | 总耗时 |
|------|---------|---------|--------|
| 扫描 | 候选 10 币串行 | lean ~8s | ~80s（30 分钟周期内充裕） |
| 跟踪 | 活跃跟踪串行 | tracking ~10s | 10 个跟踪 ~100s |
| 对话 | 单线程即时 | full ~22s | SSE 推中间状态 |

---

## 六、复盘学习机制

### 6.1 核心思路

**轻量路线**：每次决策记录快照 → 定期复盘验证 → 沉淀经验文本 → 下轮决策由经验复盘师检索。

不引入向量库、不做参数自动微调，**经验是 LLM 可读的自然语言文本 + 结构化标签**。

### 6.2 经验生命周期

```
决策时刻
     │  orchestrator.run() 完成
     ▼
decisions 表写入决策快照:
 - decision_id, symbol, direction, entry/sl/tp
 - confidence, tags, full_card_json
 - status: open
     │
     │  追踪器每 1h 检查一次
     ▼
检测决策是否落幕:
 - 价格触达止盈 → status=win
 - 价格触达止损 → status=loss
 - 超时 7 天未触达 → status=expired (拿当下盈亏作为结果)
     │
     │  每天凌晨复盘扫描
     ▼
retrospective_runner 复盘:
 - 取近 24h 落幕的决策
 - LLM: "这次决策为什么赢/输? 哪些 Mate 判断准了/偏了?
         有没有可以学习的经验?"
 - 输出 lesson 文本 + tags
     │
     ▼
experiences 表写入经验条目(聚合更新,而非 1 决策 1 经验)
     │
     │  下次决策时
     ▼
experience Mate 检索:
 - 用当前 DataPack 的 tags 匹配
 - 检索近 90 天命中标签的经验
 - 排序: 优先 outcome 明确的
 - top 5 经验文本注入 prompt
```

### 6.3 标签体系（场景指纹）

每次决策由 data_packer 自动打标签：

| 标签维度 | 取值示例 |
|---------|---------|
| `coin_tier` | large / mid / small |
| `funding` | extreme_high / extreme_low / trending_up / trending_down / normal |
| `smart_money` | extreme_long / extreme_short / divergence / quiet_buildup / normal |
| `long_short_div` | strong_div / weak_div / aligned |
| `volatility` | compressed / expanding / normal |
| `trend_alignment` | all_bullish / all_bearish / mixed / 1h_diverge |
| `volume` | spike_buy / spike_sell / shrink / normal |
| `macro_regime` | bull / bear / range |

每次决策记录 5-8 个标签作为"场景指纹"。

### 6.4 经验条目结构

```json
{
  "experience_id": 17,
  "created_at": "2026-05-10",
  "tags": ["funding=extreme_high", "smart_money=divergence",
           "volatility=compressed", "trend_alignment=mixed"],
  "scenario_summary": "高费率 + 大户散户分歧 + 波动压缩",
  "decisions_referenced": [42, 45, 51],
  "outcome_stats": { "win": 2, "loss": 1, "expired": 0 },
  "lesson": "在高费率 + 散户单边偏多 + 大户偏空场景下,反向入场胜率较高,但需等待波动压缩突破方向确认后再进,否则容易被假突破打止损。",
  "applicable_when": "费率 > 0.01% 且 大户散户多空比差 > 0.8 且 BB 带宽 < 30 分位",
  "caveats": "BTC 主导率快速变化时此规律失效"
}
```

经验是**聚合**的：复盘时如果发现某场景已有经验，会更新该经验（追加 decision_id、修正 lesson、调整 outcome_stats），而不是新建。

### 6.5 经验 Mate 在第 1 轮的工作流

```
experience Mate 收到 DataPack:
  1. 提取当前 DataPack 的标签
  2. 查 experiences 表:
     SELECT * FROM experiences
     WHERE 任一标签命中 当前标签集
       AND created_at > now - 90 days
     ORDER BY (匹配标签数 DESC, outcome 明确度 DESC)
     LIMIT 5
  3. 把命中的经验文本注入 prompt
  4. LLM 输出: "本次场景与历史经验 #17 高度匹配,该场景过去
                3 次胜 2 负,建议..."
```

### 6.6 数据库新增表

```sql
-- 决策快照
CREATE TABLE decisions (
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  trigger_mode TEXT,          -- chat / scan / tracking
  direction TEXT,
  entry_price REAL,
  stop_loss REAL,
  take_profit REAL,
  confidence INTEGER,
  tags TEXT,                  -- JSON 数组
  card_json TEXT,             -- 完整决策卡片
  audit_path TEXT,            -- tracks/decision_<id>.json
  status TEXT,                -- open / win / loss / expired
  closed_at TEXT,
  realized_pnl_pct REAL,
  created_at TEXT
);
CREATE INDEX idx_dec_symbol ON decisions(symbol);
CREATE INDEX idx_dec_status ON decisions(status);

-- 经验库
CREATE TABLE experiences (
  experience_id INTEGER PRIMARY KEY AUTOINCREMENT,
  tags TEXT,                  -- JSON 数组
  scenario_summary TEXT,
  decisions_referenced TEXT,  -- JSON 数组
  outcome_stats TEXT,         -- JSON {win,loss,expired}
  lesson TEXT,
  applicable_when TEXT,
  caveats TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX idx_exp_updated ON experiences(updated_at);

-- 对话历史
CREATE TABLE chat_messages (
  msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT,
  role TEXT,                  -- user / assistant
  content TEXT,
  decision_id INTEGER,        -- 若关联决策
  created_at TEXT
);
CREATE INDEX idx_chat_session ON chat_messages(session_id);
```

### 6.7 复盘调度

`retrospective_runner.py` 由 `start.py` 每天凌晨触发：

```python
# 伪代码
def run_daily():
    closed = db.query("SELECT * FROM decisions
                       WHERE status IN ('win','loss','expired')
                         AND closed_at > yesterday")
    grouped = group_by_tag_signature(closed)
    for tag_sig, decisions in grouped.items():
        existing = find_experience_by_tags(tag_sig)
        if existing:
            update_experience(existing, decisions)  # LLM 调一次
        else:
            create_experience(tag_sig, decisions)   # LLM 调一次
```

### 6.8 第一阶段冷启动策略

- **第 1 个月**：only 记录 decisions，不开启 experience Mate
- **第 2 个月**：experiences 数据 ≥ 30 条后，启用 experience Mate
- **第 3 个月**：根据效果决定是否引入向量化检索（暂不做）

---

## 七、LLM 抽象层 & 配置体系

### 7.1 LLM 抽象层

```python
# core/llm_client.py

class LLMResponse:
    text: str
    usage: dict   # {"prompt_tokens", "completion_tokens", "total_tokens"}
    model: str
    raw: dict     # 原始响应,审计用

class LLMClient:
    def chat(
        self,
        model: str,             # "deepseek-chat" / "claude-sonnet-4-6" / ...
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_format: str = None,   # "json" 或 None
        timeout: int = 30,
    ) -> LLMResponse: ...
```

按 `model` 前缀分发到 provider：
- `deepseek-*` → `providers/deepseek.py`（**第一阶段唯一实现**）
- `claude-*` → `providers/claude.py`（接口预留）
- `gpt-*` → `providers/openai.py`（接口预留）

### 7.2 全局配置 (config.yaml)

```yaml
# 全局
default_model: deepseek-chat
audit_dir: tracks/
data_db: funding_rate.db

# Provider
providers:
  deepseek:
    api_key_env: DEEPSEEK_API_KEY
    base_url: https://api.deepseek.com
    models: [deepseek-chat, deepseek-reasoner]
  # claude / openai 第一阶段不接,接口预留

# 币安(仅用于提高 API 限额,不下单不读账户)
binance:
  api_key_env: BINANCE_API_KEY
  api_secret_env: BINANCE_API_SECRET
  use_signed_for_quota: true

# Mate 配置
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
    enabled: false              # 冷启动期关闭
    prompt_file: prompts/experience.md
  red_team:
    model: deepseek-chat
    temperature: 0.5            # 鼓励发散
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
    temperature: 0.1            # 仓位计算要稳定
    enabled: true
    prompt_file: prompts/position_mgr.md
  decision_lead:
    model: deepseek-chat
    temperature: 0.2
    enabled: true
    prompt_file: prompts/decision_lead.md

# 模式档位
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

# 调度
scheduler:
  scan_interval_min: 30
  tracking_interval_min: 15
  retrospective_cron: "0 3 * * *"   # 每天凌晨 3 点
  scan_max_candidates: 10
  scan_min_score: 30                # 旧 signals.py 预筛阈值

# 推送
push:
  server_chan:
    enabled: true
    key_env: SERVER_CHAN_KEY        # 用户后续填入
  push_modes: [chat_decisions, scan_results, tracking_alerts]
  cooldown_min: 240                 # 同币种推送冷却 4h

# 默认参数 (mate 没设时回落到这里)
defaults:
  temperature: 0.3
  max_tokens: 2000
  timeout_sec: 30
  retry_max: 2
```

### 7.3 Prompt 模板组织

```
prompts/
  ├── trend_multi_tf.md
  ├── funding_rate.md
  ├── smart_money.md
  ├── long_short_compare.md
  ├── volatility.md
  ├── experience.md
  ├── red_team.md
  ├── macro_sentiment.md
  ├── liquidity.md
  ├── position_mgr.md
  ├── decision_lead.md
  └── _shared/
      ├── output_schema.md      # 通用输出 schema
      ├── data_pack_format.md   # DataPack 格式
      └── role_persona.md       # 通用角色规范
```

每个 Mate 的 prompt 文件结构：

```markdown
## 角色
你是 [角色名]，专注于 [职责]。

## 输入
你将收到统一的 DataPack 数据包。
{{ data_pack_format }}

## 关注维度
- [...]

## 输出格式
严格按以下 JSON 格式返回(不要任何额外说明):
{{ output_schema }}

## 评分标准
- confidence 0-100: [...]
- view: [...]

## 数据
{{ data_pack_json }}
```

模板用简单的字符串替换（不引入 Jinja2）。

### 7.4 审计落盘

```
tracks/
  ├── chat_<session_id>_<msg_id>.json     # 用户对话
  ├── decision_<decision_id>.json         # 决策审计
  ├── scan_<timestamp>.json               # 扫描审计
  ├── tracking_<symbol>_<track_id>.json   # 持仓跟踪审计
  └── retro_<date>.json                   # 复盘审计
```

每个审计文件记录完整 LLM 交互（model / prompt / response / tokens / 时间戳）。

### 7.5 配置热加载

`config.yaml` 在 `start.py` 启动时加载到内存。**修改配置需重启**。

调试用 CLI：

```bash
# 干跑某个 Mate (不入库,只看输出)
python -m agent_system.cli dry_run --symbol ETHUSDT --mate trend_multi_tf

# 跑完整流程 (不入库)
python -m agent_system.cli dry_run --symbol ETHUSDT --mode full

# 切换某个 Mate 的模型试试
python -m agent_system.cli dry_run --symbol ETHUSDT --mate red_team \
    --model deepseek-reasoner
```

---

## 八、项目目录结构

```
agent_system/                          # 全新项目根目录
├── config.yaml
├── start.py                           # 一键启动: web + scan + tracking + retro
├── requirements.txt
│
├── core/                              # 核心层
│   ├── orchestrator.py                # 三轮辩论编排
│   ├── llm_client.py                  # LLM 抽象
│   ├── data_packer.py                 # DataPack 聚合
│   ├── audit_logger.py                # 审计落盘
│   └── config_loader.py
│
├── providers/                         # LLM 供应商
│   ├── deepseek.py                    # 第一阶段唯一实现
│   ├── claude.py                      # 接口预留
│   └── openai.py                      # 接口预留
│
├── mates/                             # Teammate 实现
│   ├── base.py                        # Mate 基类
│   ├── trend_multi_tf.py
│   ├── funding_rate.py
│   ├── smart_money.py
│   ├── long_short_compare.py
│   ├── volatility.py
│   ├── experience.py
│   ├── red_team.py
│   ├── macro_sentiment.py
│   ├── liquidity.py
│   ├── position_mgr.py
│   └── decision_lead.py               # 系统级,被 orchestrator 直接调
│
├── prompts/                           # Prompt 模板
│   ├── trend_multi_tf.md
│   ├── ... (每个 mate 一个)
│   └── _shared/
│       ├── output_schema.md
│       ├── data_pack_format.md
│       └── role_persona.md
│
├── runners/                           # 三种触发模式
│   ├── chat_runner.py
│   ├── scan_runner.py
│   ├── tracking_runner.py
│   └── retrospective_runner.py
│
├── data/                              # 数据访问
│   ├── db.py                          # 复用旧 db.py + 新增表 init
│   ├── binance_client.py              # 币安签名版
│   ├── experience_store.py
│   └── decisions_store.py
│
├── web/                               # Web 服务
│   ├── app.py                         # Flask 路由
│   ├── chat_api.py                    # 对话 API + SSE
│   ├── debate_api.py                  # 辩论流推送
│   ├── static/
│   └── templates/
│       └── chat.html                  # 全新对话主页
│
├── push/
│   └── server_chan.py
│
├── cli/
│   └── __main__.py                    # python -m agent_system.cli
│
├── tests/
│   ├── test_data_packer.py
│   ├── test_orchestrator.py
│   └── ...
│
└── tracks/                            # 审计目录(共用旧目录)
```

### 8.1 复用 / 废弃 / 新建 — 全文件清单

| 文件 | 处置 | 说明 |
|------|------|------|
| `funding_rate.py` (旧) | **复用** | 公开接口仍可用，binance_client.py 是新版（签名 + 限额提升） |
| `db.py` (旧) | **部分复用** | 表结构保留，agent_system/data/db.py 引用并扩展 |
| `fetch_funding_data.py` | **复用** | 数据采集脚本不变 |
| `fetch_kline_data.py` | **复用** | 同上 |
| `fetch_position_data.py` | **复用** | 同上 |
| `coin_groups.py` | **复用** | scan_runner 用它做币种分组 |
| `signals.py` | **复用为预筛子** | scan_runner 调它做候选筛选 |
| `backtest.py` | **保留不动** | 第一阶段不集成,但保留作为后续验证工具 |
| `monitor.py` (旧) | **废弃** | 调度逻辑被 runners/ 替代 |
| `app.py` (旧) | **废弃** | Web 替换为 agent_system/web/app.py |
| `start.py` (旧) | **废弃** | 替换为 agent_system/start.py |
| `templates/index.html` | **废弃** | 替换为 chat.html |
| `templates/backtest.html` | **保留** | 回测页保留 |
| `tracks/` (目录) | **复用** | 沿用并扩展 |
| `funding_rate.db` | **复用** | 表结构兼容,新表叠加 |

废弃的文件**不删除**，留作参考。

### 8.2 启动入口

```bash
cd agent_system
python start.py
```

`start.py` 同时启动：
1. Flask Web (端口 5000) — chat.html 与 API
2. scan_runner（30 分钟周期）
3. tracking_runner（15 分钟周期）
4. retrospective_runner（每天 03:00 cron）

Ctrl+C 一键全停。

### 8.3 环境变量

```bash
# 必须
DEEPSEEK_API_KEY=sk-xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# 可选
SERVER_CHAN_KEY=SCT-xxx           # 不设则不推送
```

---

## 九、实施路线图

分 5 个阶段递进，每阶段都有可独立验证的产物。

### Phase 1 — 基础设施与单 Mate 跑通（约 2-3 天）

**目标**：CLI 跑通"输入 ETHUSDT → DataPack → 1 个 Mate → 输出 JSON"。

- [ ] 项目脚手架（目录、`config.yaml`、`requirements.txt`）
- [ ] `core/llm_client.py` + `providers/deepseek.py`
- [ ] `core/config_loader.py`（加载 YAML，回落 defaults）
- [ ] `core/audit_logger.py`（写 JSON 审计）
- [ ] `data/binance_client.py`（接币安 API，带签名提高限额）
- [ ] `data/db.py`（复用旧 db，新增 3 张表 init）
- [ ] `data/data_packer.py`（聚合 K线/费率/持仓/多空比/ATR/布林）
- [ ] `mates/base.py`（Mate 基类：load prompt、render、call llm、parse JSON）
- [ ] `mates/trend_multi_tf.py`（先实现一个最简单的）
- [ ] `prompts/trend_multi_tf.md` + `prompts/_shared/*.md`
- [ ] `cli/__main__.py` 的 `dry_run --symbol --mate` 命令
- [ ] 单元测试：data_packer、llm_client、base.Mate

**验收**：`python -m agent_system.cli dry_run --symbol ETHUSDT --mate trend_multi_tf` 输出合法 JSON。

### Phase 2 — 完整 11 Mate + 三轮辩论（约 3-4 天）

**目标**：CLI 跑通 `full` 模式完整决策卡片。

- [ ] 写完其他 9 个 Mate（experience 留空壳）
- [ ] 写完 9 个对应 prompt
- [ ] `core/orchestrator.py`：3 轮编排逻辑（含 round_2 majority 统计、调度被点名 Mate）
- [ ] `mates/decision_lead.py`（第 3 轮综合决策）
- [ ] `mates/position_mgr.py` 后置触发逻辑（Batch 2 在 Batch 1 完成后才跑）
- [ ] 决策卡片 schema 校验
- [ ] 异常降级：单 Mate 超时/JSON 非法时跳过 + 审计标记
- [ ] CLI `dry_run --mode full` 命令
- [ ] 集成测试：跑 3 个真实 symbol（如 ETH/BTC/小盘币），人工评估输出合理性

**验收**：CLI 三轮跑通，决策卡片含完整字段，审计文件结构完整。

### Phase 3 — Web 对话 + 三种触发模式（约 4-5 天）

**目标**：上线对话主页，三种触发模式都跑起来。

- [ ] `web/app.py` Flask 骨架
- [ ] `web/chat_api.py`：POST /api/chat（创建会话、发送消息）
- [ ] `web/debate_api.py`：GET /api/debate/<decision_id>/stream（SSE 流）
- [ ] `runners/chat_runner.py`：意图解析 + 调度 orchestrator
- [ ] `runners/scan_runner.py`：复用 signals.py 预筛 + 调 orchestrator(lean)
- [ ] `runners/tracking_runner.py`：复用旧跟踪结构 + 调 orchestrator(tracking)
- [ ] `templates/chat.html`：三栏布局（左：扫描+跟踪 / 中：对话 / 右：辩论流）
- [ ] `push/server_chan.py`：推送决策卡片
- [ ] `start.py`：一键启动 Web + 三 runner
- [ ] 端到端验证：在浏览器问 "ETH 怎么样"，看到辩论流 + 决策卡片

**验收**：浏览器全流程跑通；定时扫描、定时跟踪都能产出推送。

### Phase 4 — 决策记录 + 复盘冷启动（约 2-3 天）

**目标**：决策入库，状态追踪，准备经验数据。

- [ ] `data/decisions_store.py`：决策快照写入
- [ ] `data/data_packer.py` 增加标签提取逻辑
- [ ] 决策状态追踪器：每 1 小时扫一次 open 决策，按价格更新 status
- [ ] `runners/retrospective_runner.py`：每日凌晨复盘扫描
- [ ] `data/experience_store.py`：经验 CRUD（聚合 / 更新 / 检索）
- [ ] `mates/experience.py` + prompt（**仍 enabled=false**）
- [ ] CLI: `python -m agent_system.cli retrospective --date YYYY-MM-DD`

**验收**：每次决策正确入库；状态追踪能把已完结的标记为 win/loss；复盘脚本能跑出经验文本。

### Phase 5 — 启用经验 Mate + 调优（持续）

**目标**：经验数据积累足够后，正式启用 experience Mate。

- [ ] 经验数据 ≥ 30 条后，把 `mates.experience.enabled` 改为 true
- [ ] 监控 experience 命中率：每次决策记录"是否命中经验、命中几条"
- [ ] 根据效果调 prompt、调 max_tokens、调标签粒度
- [ ] 视效果决定是否引入向量检索（**第二阶段**，暂不做）

**验收**：经验 Mate 启用后 1 个月，胜率有可观察的趋势变化。

### 9.6 整体约束与验证

每阶段完成都跑：
- 单元测试通过
- 至少 1 次端到端 dry run（真实 API）
- 审计文件检查（无残缺、无 JSON 解析错误）

### 9.7 第一阶段不做

- 多用户隔离（单用户系统）
- 接 L2 订单簿数据（liquidity Mate 用近似）
- 自动下单（手动入场，币安 API 仅用于提高限频）
- Web UI 优化（先功能跑通，丑可以接受）
- 向量化经验检索（用 SQL 标签匹配先跑起来）
- 接 Claude / OpenAI（DeepSeek 单家先跑通）

### 9.8 风险与应对

| 风险 | 应对 |
|------|------|
| 单次决策 LLM 调用 ~15 次，成本/延迟可能超预期 | Phase 2 完成后实测；超标就先降到 lean 模式或缩 max_tokens |
| 11 Mate 并行打 DeepSeek 触发限流 | 触发限流则改成串行 + 指数退避 |
| Mate 输出 JSON 解析失败率高 | base.Mate 加重试 + JSON 修复 prompt + fallback 默认值 |
| 经验 Mate 过早启用产生噪音 | 强制冷启动期（Phase 4 至少 30 天）不开启 |
| 旧 signals.py 预筛与 Agent Team 判断不一致 | 这是预期内的，预筛只决定"是否进入深度分析"，最终由 Team 出决策 |

---

## 十、附录

### 10.1 名词对照

| 名词 | 含义 |
|------|------|
| Mate / Teammate | 圆桌中的某个专业分析师 Agent |
| Lead / Orchestrator | 主持讨论、调度 Mate、综合决策的角色 |
| DataPack | 单次决策时聚合的统一市场数据包 |
| 决策卡片 | 第 3 轮 Lead 输出的结构化结果 |
| 经验 / Experience | 复盘后沉淀到经验库的自然语言文本条目 |
| 标签 / Tags | DataPack 自动提取的场景指纹，用于经验检索 |
| 模式档位 | full / lean / tracking 三档运行配置 |
| 预筛子 | 旧 signals.py 在新系统中的角色：扫描时做规则筛选，缩小 Agent Team 处理量 |

### 10.2 与旧系统的关键差异

| 维度 | 旧系统 | 新系统 |
|------|--------|--------|
| 触发 | 仅定时 | 对话 + 定时扫描 + 跟踪 |
| 决策 | 规则打分 + 单次 LLM | 11 Mate 三轮辩论 |
| 周期 | 单一窗口 | 多周期协同（1h/4h/1d/1w） |
| 扩展 | 改 signals.py | 加 prompt + config 一行 |
| 学习 | 无 | 决策快照 + 经验聚合 + 检索 |
| 推送 | 简单消息 | 决策卡片紧凑式 |
