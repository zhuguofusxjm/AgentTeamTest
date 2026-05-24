# Agent Team 量化分析系统

币安 U 本位永续合约智能体分析系统 — 12 位分析师圆桌辩论 + 经验复盘。

> 设计文档：`docs/superpowers/specs/2026-05-16-agent-team-design.md`
> 实施记录：`docs/superpowers/plans/2026-05-16-agent-team-system.md`

## 12 位分析师团队

| 中文角色 | mate_id | 职责 |
|---|---|---|
| 周期师 | trend_multi_tf | 1h/4h/1d/1w 多周期趋势协同 |
| 费率官 | funding_rate | 资金费率绝对值/分位/跨币对比 |
| 大户雷达 | smart_money | 大户持仓比 + OI 增长 + 主买卖 |
| 多空裁 | long_short_compare | 大户 vs 全市场多空比背离 |
| 波动官 | volatility | ATR 比值 + 布林带带宽分位 |
| 结构师 | smc_structure | SMC 结构 (BOS/CHoCH/OB/FVG/EQH-EQL/Premium-Discount) |
| 复盘官 | experience | 检索经验库历史样本 (默认停用) |
| 投资风险师 | red_team | 列举风险路径 + 反驳多数派 |
| 宏观官 | macro_sentiment | BTC 主导率 + 大盘 regime |
| 水位官 | liquidity | 成交量放缩 + OI 变化 |
| 仓位管家 | position_mgr | 综合各方观点算止损/止盈/仓位 |
| 决策长 | decision_lead | 综合三轮辩论产出最终决策卡片 |

## 圆桌流程

```
用户消息
   ↓
意图解析 (single_analysis / follow_up / data_query / chitchat)
   ↓
DataPack 拉取  (4 周期 K 线 + 费率 + 持仓 + 指标 + 跨币种)
   ↓
[第 1 轮 独立分析]   ── 9 位分析师并行,各自 view + confidence
[第 2 轮 反驳]       ── 投资风险师反驳多数派 → top3 回应
[第 3 轮 综合]       ── 决策长产出决策卡片
   ↓
入库 + 审计 JSON 落盘 + Server酱 推送(可选)
```

## 快速开始

```bash
# 1. 环境变量
export DEEPSEEK_API_KEY=sk-xxx
export BINANCE_API_KEY=xxx
export BINANCE_API_SECRET=xxx
export SERVER_CHAN_KEY=SCT-xxx   # 可选

# 2. 装依赖
pip install -r agent_system/requirements.txt

# 3. 启动 (Web + scan + tracking + status_tracker + retro 一起跑)
python -m agent_system.start
```

打开 http://localhost:5000:

- **顶部** 系统状态栏:运行状态 / 决策统计 / 活跃跟踪数 / 分析师团队介绍按钮
- **中部** 决策列表:
  - 过滤 tab(全部/扫描/对话/跟踪)
  - 搜索栏(日期范围/币种/方向/信心/状态)
  - 表格(时间/币种/类型/方向/详情/信心/状态/辩论流)
  - 分页(每页 20 条)
- **右侧抽屉** 辩论流:点击"辩论流"按钮滑出,回放 12 位分析师每轮输出
- **右下角** AI 聊天面板:默认收起,点击 💬 展开;输入"帮我分析 ETH"发起圆桌

支持多轮对话:决策出来后,可继续追问 "你们有几个分析师?各自结论?为什么?有什么风险?",会基于真实 audit 数据自然回答。

## 命令行调试

```bash
# 跑单个分析师
python -m agent_system.cli dry_run --symbol ETHUSDT --mate trend_multi_tf

# 跑完整 12 Mate 三轮辩论
python -m agent_system.cli dry_run --symbol ETHUSDT --mode full

# 跑 lean 模式(2 轮,更省 token)
python -m agent_system.cli dry_run --symbol ETHUSDT --mode lean

# 切换模型
python -m agent_system.cli dry_run --symbol ETHUSDT --mate red_team --model deepseek-reasoner

# 手动触发每日复盘 (默认每天凌晨 3 点自动跑)
python -m agent_system.cli retrospective

# 检查复盘官 (experience Mate) 是否可启用
python -m agent_system.cli.check_ready
```

## 三种触发模式

| 模式 | 触发 | Mate 集 | 轮数 |
|---|---|---|---|
| `chat` | 用户 web 对话 | full (12 位) | 3 |
| `scan` | 4h 定时扫描全市场 top 候选 | lean (7 位) | 2 |
| `tracking` | 1h 跟踪已开仓位 | tracking (7 位) | 2 |

### Scan 候选预筛("先大后偏")

1. **第一层(体量)**: 全市场 USDT 永续按 24h 成交额倒序,取 Top 30
2. **第二层(五类极端)** 在 Top 30 里各取 10:
   - 资金费率最极端(拥挤)
   - 大户多空比最极端(站队)
   - 24h 涨跌幅最大(动量)
   - OI 增长率最高(资金涌入)
   - 成交量异动(24h vs 7d 均值)
3. 五类并集去重 → 截到 `scan_max_candidates`(默认 10)进圆桌

### 决策胜负判定

逐根 1h K 线按时间顺序扫描,**先触发者为准**:
- 多头:某根 low ≤ SL → loss;某根 high ≥ TP → win
- 空头:某根 high ≥ SL → loss;某根 low ≤ TP → win
- 同一根内 SL/TP 都触发 → 保守判 loss(无法确定 tick 级先后)
- 7 天内都没触发 → expired,按最终 close 结算

每次决策都会:
1. 落盘 audit JSON 到 `tracks/decision_<symbol>_<ts>.json`
2. 写入 `decisions` 表(SQLite)
3. 触发 Server酱 推送(若已配置)

## 后台循环

`start.py` 启动后跑 4 条循环:

| 循环 | 频率 | 用途 |
|---|---|---|
| scan_loop | 4h | 扫描候选币种(5 维预筛),产出决策推送 |
| tracking_loop | 1h | 跟踪已开仓位,触发出场建议 |
| status_loop | 1h | 逐根 K 线判定 open 决策有无触发 SL/TP/超时 |
| retro_loop | 凌晨 3 点 | 按场景 tag 分组复盘已结决策,沉淀经验 |

## 复盘怎么工作

每天凌晨 3 点(也可手动 `python -m agent_system.cli retrospective`):

1. 取过去 24h 内 `closed_at` 命中的所有 `win/loss/expired` 决策
2. 按 `tags` 分组(如 `funding=normal + smart_money=normal + volatility=compressed`)
3. 对每组:
   - 重新拉决策期间的真实 K 线,算 **MFE/MAE/path_shape/time_to_close**
   - 从 audit JSON 提取 12 位分析师当时各自的 view+confidence
   - 喂给 LLM 做归因:哪些分析师在该场景可信、哪些误导、止损是否过紧、是否假突破
   - 输出 `lesson` 追加到经验库(带日期 + 样本统计)
4. 新组样本不足 3 条时跳过,避免单样本噪声

经验库累积 30 条后,运行 `check_ready` 提示启用复盘官,把历史经验注入下一次决策。

## 启用复盘官 (experience Mate)

```bash
python -m agent_system.cli.check_ready
# 输出 "经验库充足" 后,改 config:
# agent_system/config.yaml 里:
# mates.experience.enabled: true
# 然后重启 python -m agent_system.start
```

## 项目结构

```
agent_system/
├── config.yaml          # 全局配置 (Mate 列表 / 模型 / 触发模式)
├── start.py             # 一键启动
├── core/
│   ├── orchestrator.py  # 三轮辩论编排 + 事件流
│   ├── llm_client.py    # 多 provider 抽象
│   ├── data_packer.py   # DataPack 聚合 + 标签提取
│   ├── data_slice.py    # Mate 切片工具 (token 节省 94%)
│   ├── audit_logger.py  # 审计 JSON 落盘
│   ├── audit_reader.py  # 提取 audit 中各 Mate round-1 view
│   └── decision_metrics.py  # MFE/MAE/path_shape 复盘指标
├── mates/               # 12 位分析师 + 中文名映射
├── prompts/             # 12 份 prompt 模板 + _shared
├── runners/             # chat / scan / tracking / status_tracker / retrospective
├── data/                # SQLite + binance + decisions/chat/tracking/experiences store
├── web/                 # Flask + SSE (上中下布局 + 搜索 + 分页 + 辩论流抽屉)
├── push/                # Server酱 推送
├── cli/                 # python -m agent_system.cli ...
├── scripts/             # 一次性修正脚本 (fix_decision_status.py)
└── tests/               # 101 个 pytest 用例
```

## Token 用量 (deepseek-chat)

每个分析师只看自己需要的字段(切片), 单次决策大约:

- **lean 模式** 7 万 in + 2000 out ≈ **0.04 元**
- **full 模式** 13 万 in + 3000 out ≈ **0.08 元**
- 每天 50 次对话 + 200 次扫描 ≈ **10 元**

模板前缀稳定, prompt cache 命中部分按 0.05 元/M 算,几乎免费。

## 开发

跑测试:
```bash
pytest agent_system/tests/ -v
```

当前 101 个用例,覆盖配置/数据库/Mate base/编排/路由/扫描预筛/跟踪/复盘/对话/SMC。
