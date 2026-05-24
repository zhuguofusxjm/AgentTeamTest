# Scan 预选维度标签 — UI 列展示

## 目标

在决策列表表格中新增"预选"列，以彩色中文徽章展示每条 scan 决策被预筛选中的维度（费率/多空/动量/OI增长/量异动），帮助用户一眼判断 setup 质量。

## 决策记录

| 问题 | 选择 |
|------|------|
| 功能范围 | A — 仅"看原因"，不做筛选/排序/归因 |
| 展示形态 | 单独一列彩色中文徽章 |
| 颜色规则 | 按维度类型固定语义色 |
| 持久化 | 新建 `prefilter_tags` 列（TEXT/JSON） |
| 透传方式 | 预筛函数返回 `list[dict]` |
| 徽章文案 | 中文短词 |
| 历史回填 | 不回填，旧记录留 NULL |
| 非 scan 来源 | 新列留空 |
| API 处理 | 后端反序列化为数组再透传 |

## 架构

```
_prefilter_by_volume_and_extremes()
   ↓ [{symbol, dims}, ...]
ScanRunner.run()
   ↓ dims 传给 save_decision
save_decision(prefilter_tags=dims)
   ↓ 写入 decisions.prefilter_tags (JSON)
/api/decisions
   ↓ 反序列化为 list[str]
chat.js
   ↓ 映射 → 彩色徽章
chat.html 新列 "预选"
```

## 数据契约

### 预筛函数返回值

```python
# _prefilter_by_volume_and_extremes() → list[dict]
[
    {"symbol": "BTCUSDT", "dims": ["funding", "oi_growth"]},
    {"symbol": "ETHUSDT", "dims": ["price"]},
]
```

dims 取值（固定 5 key）：`funding` / `position` / `price` / `oi_growth` / `volume_anomaly`

### save_decision 签名

```python
save_decision(db_path, symbol, trigger_mode, card, tags, audit_path,
              prefilter_tags: list[str] | None = None)
```

### DB 列

```sql
ALTER TABLE decisions ADD COLUMN prefilter_tags TEXT;
-- 值: '["funding","oi_growth"]' 或 NULL
```

### API 返回

```jsonc
{
  "prefilter_tags": ["funding", "oi_growth"]  // 已反序列化; chat/tracking 为 null
}
```

### 前端映射常量

```js
const PREFILTER_DIM_LABEL = {
  funding:        { text: '费率',   color: '#e74c3c' },
  position:       { text: '多空',   color: '#f39c12' },
  price:          { text: '动量',   color: '#3498db' },
  oi_growth:      { text: 'OI增长', color: '#9b59b6' },
  volume_anomaly: { text: '量异动', color: '#27ae60' },
};
```

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `runners/scan_runner.py` | 返回值改 list[dict]；内部维护 dim_map |
| `data/decisions_store.py` | save_decision 加参数；list_decisions_paginated 反序列化 |
| `data/db.py` 或迁移脚本 | ALTER TABLE 加列（幂等） |
| `web/templates/chat.html` | 表头加"预选"列 |
| `web/static/chat.js` | 渲染徽章 + 映射常量 |
| `web/static/chat.css` | `.prefilter-badge` 样式 |
| `tests/test_scan_prefilter.py` | 验证新返回形状 |

## 错误处理

- 某维度 API 失败 → 该 symbol 的 dims 少一个 key，不影响其他维度
- prefilter_tags=None → DB 存 NULL，API 返回 null，前端留空
- DB 列值非法 JSON → 反序列化 fallback 为 None
- 前端遇到未知 key → 显示原始 key + 灰色背景

## 测试

### 单元测试（扩展 test_scan_prefilter.py）
- 返回值为 list[dict]，每项含 symbol(str) + dims(list[str])
- 多维度命中时 dims 包含所有 key
- 未命中 symbol 不出现

### 单元测试（decisions_store）
- save + read 往返：prefilter_tags=["funding","price"] → 读回为 list
- prefilter_tags=None → 读回为 None

### 手动验证
- scan 决策：新列显示彩色徽章
- chat/tracking 决策：新列空白
- 旧历史记录：新列空白
- 窄屏多维度命中时徽章不溢出
