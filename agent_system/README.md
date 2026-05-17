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

参见 `docs/superpowers/plans/2026-05-16-agent-team-system.md` 中的"文件结构"小节。

## 启用 experience Mate

1. 系统跑满 30 天,生成 ≥ 30 条经验
2. 运行 `python -m agent_system.cli.check_ready` 验证
3. 修改 `agent_system/config.yaml`: `mates.experience.enabled: true`
4. 重启 `python -m agent_system.start`
