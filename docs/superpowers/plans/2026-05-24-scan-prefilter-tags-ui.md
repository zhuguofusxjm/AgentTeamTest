# Scan 预选维度标签 UI 列 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在决策列表新增"预选"列，以彩色中文徽章展示每条 scan 决策被预筛选中的维度。

**Architecture:** 预筛函数返回 `list[dict]` 携带命中维度 → ScanRunner 透传给 save_decision → 新增 DB 列 `prefilter_tags` 持久化 → API 反序列化 → 前端渲染彩色徽章。

**Tech Stack:** Python 3 / SQLite / Jinja2 / Vanilla JS / CSS

---

## File Map

| File | Responsibility |
|------|---------------|
| `agent_system/data/db.py` | DDL + 迁移（新增列） |
| `agent_system/data/decisions_store.py` | 写入 + 读取反序列化 |
| `agent_system/runners/scan_runner.py` | 预筛返回 list[dict] + 透传 dims |
| `agent_system/web/templates/chat.html` | 表头新增列 |
| `agent_system/web/static/chat.js` | 渲染徽章 |
| `agent_system/web/static/chat.css` | 徽章样式 |
| `agent_system/tests/test_scan_prefilter.py` | 预筛返回形状测试 |

---

### Task 1: DB 迁移 — 新增 prefilter_tags 列

**Files:**
- Modify: `agent_system/data/db.py:27` (在 DDL_DECISIONS 后加迁移常量)
- Modify: `agent_system/data/db.py:87-103` (init_new_tables 中执行迁移)

- [ ] **Step 1: 在 db.py 中添加迁移 SQL 常量**

在 `DDL_DECISIONS_IDX_STATUS` 之后添加：

```python
DDL_MIGRATE_PREFILTER_TAGS = """
ALTER TABLE decisions ADD COLUMN prefilter_tags TEXT
"""
```

- [ ] **Step 2: 在 init_new_tables 中幂等执行迁移**

在 `conn.execute(DDL_DECISIONS_IDX_STATUS)` 之后添加：

```python
existing = {row[1] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()}
if "prefilter_tags" not in existing:
    conn.execute(DDL_MIGRATE_PREFILTER_TAGS)
```

- [ ] **Step 3: 手动验证迁移**

Run: `cd agent_system && python -c "from data.db import init_new_tables; init_new_tables('test_migrate.db'); import sqlite3; c=sqlite3.connect('test_migrate.db'); print([r[1] for r in c.execute('PRAGMA table_info(decisions)').fetchall()])"`
Expected: 列表中包含 `'prefilter_tags'`

- [ ] **Step 4: 清理测试文件并提交**

```bash
rm -f agent_system/test_migrate.db
git add agent_system/data/db.py
git commit -m "feat(db): add prefilter_tags column to decisions table"
```

---

### Task 2: decisions_store — save_decision 支持 prefilter_tags

**Files:**
- Modify: `agent_system/data/decisions_store.py:5-21`

- [ ] **Step 1: 修改 save_decision 签名和 INSERT**

将 `save_decision` 改为：

```python
def save_decision(db_path, symbol, trigger_mode, card, tags, audit_path,
                  prefilter_tags=None) -> int:
    conn = get_conn(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO decisions (symbol, trigger_mode, direction, entry_price,
               stop_loss, take_profit, confidence, tags, card_json, audit_path,
               prefilter_tags, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (symbol, trigger_mode, card.get("direction"),
             card.get("entry_price"), card.get("stop_loss"), card.get("take_profit"),
             card.get("confidence"), json.dumps(tags, ensure_ascii=False),
             json.dumps(card, ensure_ascii=False), audit_path,
             json.dumps(prefilter_tags, ensure_ascii=False) if prefilter_tags else None,
             datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
```

- [ ] **Step 2: 验证现有测试不被破坏**

Run: `cd agent_system && python -m pytest tests/ -v --tb=short 2>&1 | head -40`
Expected: 所有已有测试 PASS（新参数有默认值，不影响旧调用）

- [ ] **Step 3: Commit**

```bash
git add agent_system/data/decisions_store.py
git commit -m "feat(store): save_decision accepts prefilter_tags param"
```

---

### Task 3: decisions_store — 读取时反序列化 prefilter_tags

**Files:**
- Modify: `agent_system/data/decisions_store.py:63-142` (list_decisions_paginated)

- [ ] **Step 1: 在 list_decisions_paginated 的 items 循环中反序列化 prefilter_tags**

在 `d["card"] = json.loads(cj)` 块之后（约第 131 行），添加：

```python
pt = d.get("prefilter_tags")
if pt:
    try:
        d["prefilter_tags"] = json.loads(pt)
    except Exception:
        d["prefilter_tags"] = None
```

- [ ] **Step 2: 验证**

Run: `cd agent_system && python -m pytest tests/ -v --tb=short 2>&1 | head -40`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add agent_system/data/decisions_store.py
git commit -m "feat(store): deserialize prefilter_tags in paginated query"
```

---

### Task 4: scan_runner — 预筛函数返回 list[dict] 并携带 dims

**Files:**
- Modify: `agent_system/runners/scan_runner.py:3-112`

- [ ] **Step 1: 重构 _prefilter_by_volume_and_extremes 返回值**

改动要点（保持内部逻辑不变，只改数据收集和返回）：

1. 在函数开头（第 29 行之前）初始化 dim_map：
```python
    dim_map = {}  # symbol -> set of dim keys
```

2. 每个分支命中后记录维度。在 `by_funding` 排序后（第 45 行后）：
```python
    for s, _ in by_funding:
        dim_map.setdefault(s, set()).add("funding")
```

3. 在 `by_pos` 排序后（第 60 行后）：
```python
    for s, _ in by_pos:
        dim_map.setdefault(s, set()).add("position")
```

4. 在 `by_price` 排序后（第 65 行后）：
```python
    for s, _ in by_price:
        dim_map.setdefault(s, set()).add("price")
```

5. 在 `by_oi` 排序后（第 84 行后）：
```python
    for s, _ in by_oi:
        dim_map.setdefault(s, set()).add("oi_growth")
```

6. 在 `by_vol` 排序后（第 105 行后）：
```python
    for s, _ in by_vol:
        dim_map.setdefault(s, set()).add("volume_anomaly")
```

7. 替换合并去重逻辑（第 107-112 行）：
```python
    seen = set()
    out = []
    for s, _ in by_funding + by_pos + by_price + by_oi + by_vol:
        if s not in seen:
            seen.add(s)
            out.append({"symbol": s, "dims": sorted(dim_map.get(s, set()))})
    return out
```

- [ ] **Step 2: 验证函数可调用**

Run: `cd agent_system && python -c "from runners.scan_runner import _prefilter_by_volume_and_extremes; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agent_system/runners/scan_runner.py
git commit -m "feat(scan): prefilter returns list[dict] with dims"
```

---

### Task 5: scan_runner — ScanRunner 调用点适配新返回值

**Files:**
- Modify: `agent_system/runners/scan_runner.py:131-178`

- [ ] **Step 1: 修改 _candidates 方法**

```python
    def _candidates(self) -> list:
        try:
            limit = self.cfg["scheduler"]["scan_max_candidates"]
            return _prefilter_by_volume_and_extremes(
                self.binance, top_volume=30,
                top_funding=10, top_position_dev=10,
                top_price_change=10, top_oi_growth=10, top_volume_anomaly=10,
            )[:limit]
        except Exception as e:
            print(f"[scan] prefilter failed: {e}; fallback")
            return [{"symbol": "BTCUSDT", "dims": []}, {"symbol": "ETHUSDT", "dims": []}]
```

- [ ] **Step 2: 修改 run_once 中的循环**

将第 157-168 行改为：

```python
        for item in candidates:
            symbol = item["symbol"] if isinstance(item, dict) else item
            dims = item.get("dims", []) if isinstance(item, dict) else []
            try:
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                card = self.orch.run(symbol=symbol, mode="lean", data_pack=pack)
                tags = pack.get("tags", [])
                audit_path = card.get("audit_path") or ""
                did = save_decision(self.db_path, symbol=symbol, trigger_mode="scan",
                                    card=card, tags=tags, audit_path=audit_path,
                                    prefilter_tags=dims if dims else None)
                card["decision_id"] = did
                cards.append(card)
            except Exception as e:
                print(f"[scan] {symbol} failed: {e}")
```

- [ ] **Step 3: 验证**

Run: `cd agent_system && python -m pytest tests/ -v --tb=short 2>&1 | head -40`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add agent_system/runners/scan_runner.py
git commit -m "feat(scan): ScanRunner passes dims to save_decision"
```

---

### Task 6: 更新测试 — 验证新返回形状

**Files:**
- Modify: `agent_system/tests/test_scan_prefilter.py`

- [ ] **Step 1: 更新 test_prefilter_combines_top_volume_funding_and_position**

将断言部分改为：

```python
    # 返回值现在是 list[dict]
    assert isinstance(candidates, list)
    symbols = [c["symbol"] for c in candidates]
    assert "BUSDT" in symbols  # 极端费率
    assert "CUSDT" in symbols  # 极端多空比
    assert "DUSDT" not in symbols  # 体量太小

    # 验证 dims 字段
    busdt = next(c for c in candidates if c["symbol"] == "BUSDT")
    assert "funding" in busdt["dims"]
    cusdt = next(c for c in candidates if c["symbol"] == "CUSDT")
    assert "position" in cusdt["dims"]
```

- [ ] **Step 2: 更新 test_prefilter_picks_price_momentum_oi_growth_and_volume_anomaly**

将断言部分改为：

```python
    assert isinstance(candidates, list)
    symbols = [c["symbol"] for c in candidates]
    assert "BUSDT" in symbols  # 涨幅极端
    assert "CUSDT" in symbols  # OI 增长极端
    assert "EUSDT" in symbols  # 成交量异动极端

    busdt = next(c for c in candidates if c["symbol"] == "BUSDT")
    assert "price" in busdt["dims"]
    cusdt = next(c for c in candidates if c["symbol"] == "CUSDT")
    assert "oi_growth" in cusdt["dims"]
    eusdt = next(c for c in candidates if c["symbol"] == "EUSDT")
    assert "volume_anomaly" in eusdt["dims"]
```

- [ ] **Step 3: 运行测试**

Run: `cd agent_system && python -m pytest tests/test_scan_prefilter.py -v`
Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add agent_system/tests/test_scan_prefilter.py
git commit -m "test: update prefilter tests for list[dict] return shape"
```

---

### Task 7: 前端 — HTML 表头新增"预选"列

**Files:**
- Modify: `agent_system/web/templates/chat.html:59-73`

- [ ] **Step 1: 在表头"币种"和"类型"之间插入新列**

将：
```html
            <th>币种</th>
            <th>类型</th>
```

改为：
```html
            <th>币种</th>
            <th>预选</th>
            <th>类型</th>
```

- [ ] **Step 2: Commit**

```bash
git add agent_system/web/templates/chat.html
git commit -m "feat(ui): add prefilter column header to decisions table"
```

---

### Task 8: 前端 — JS 渲染徽章

**Files:**
- Modify: `agent_system/web/static/chat.js:176-214`

- [ ] **Step 1: 在 chat.js 顶部（或 renderTable 之前）添加映射常量**

```js
const PREFILTER_DIM_LABEL = {
  funding:        { text: '费率',   color: '#e74c3c' },
  position:       { text: '多空',   color: '#f39c12' },
  price:          { text: '动量',   color: '#3498db' },
  oi_growth:      { text: 'OI增长', color: '#9b59b6' },
  volume_anomaly: { text: '量异动', color: '#27ae60' },
};
```

- [ ] **Step 2: 在 renderTable 的 return 模板中，"币种"td 之后插入新列**

在 `<td><b>${d.symbol}</b></td>` 之后、`<td><span class="trigger-badge...` 之前插入：

```js
      <td class="prefilter-cell">${(d.prefilter_tags || []).map(k => {
        const dim = PREFILTER_DIM_LABEL[k] || { text: k, color: '#94a3b8' };
        return `<span class="prefilter-badge" style="background:${dim.color}">${dim.text}</span>`;
      }).join("")}</td>
```

- [ ] **Step 3: Commit**

```bash
git add agent_system/web/static/chat.js
git commit -m "feat(ui): render prefilter dim badges in decisions table"
```

---

### Task 9: 前端 — CSS 徽章样式

**Files:**
- Modify: `agent_system/web/static/chat.css`

- [ ] **Step 1: 在 chat.css 末尾添加徽章样式**

```css
/* Prefilter dimension badges */
.prefilter-cell { white-space: nowrap; }
.prefilter-badge {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
  margin-right: 3px;
  margin-bottom: 2px;
}
```

- [ ] **Step 2: 启动 dev server 验证**

Run: `cd agent_system && python web/app.py`
打开浏览器访问决策列表页面，确认：
- scan 决策行显示彩色中文徽章
- chat/tracking 决策行新列为空
- 多维度命中时徽章并排不溢出

- [ ] **Step 3: Commit**

```bash
git add agent_system/web/static/chat.css
git commit -m "feat(ui): prefilter badge styles"
```
