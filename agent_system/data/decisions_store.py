import json
from datetime import datetime
from agent_system.data.db import get_conn

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

def get_decision(db_path, decision_id) -> dict:
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def list_open_decisions(db_path) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute("SELECT * FROM decisions WHERE status = 'open'").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_decision_status(db_path, decision_id, status, realized_pnl_pct=None):
    conn = get_conn(db_path)
    try:
        conn.execute(
            """UPDATE decisions SET status = ?, closed_at = ?, realized_pnl_pct = ?
               WHERE decision_id = ?""",
            (status, datetime.now().isoformat(), realized_pnl_pct, decision_id),
        )
        conn.commit()
    finally:
        conn.close()

def list_recent_decisions(db_path, limit=50) -> list:
    conn = get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY decision_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_decisions_paginated(db_path, page: int = 1, page_size: int = 20,
                             trigger_mode: str = None, symbol: str = None,
                             direction: str = None, status: str = None,
                             confidence_min: int = None,
                             date_start: str = None, date_end: str = None) -> dict:
    """分页查询决策,支持多条件组合搜索。

    参数:
        page: 1-based 页码
        page_size: 每页条数(默认 20,最大 100)
        trigger_mode: scan/chat/tracking
        symbol: 币种模糊匹配(LIKE '%symbol%')
        direction: 多/空/观望
        status: open/win/loss/expired
        confidence_min: 信心下限(>=)
        date_start: 开始日期 'YYYY-MM-DD'
        date_end: 结束日期 'YYYY-MM-DD'(含当天)

    返回:
        {"items": [...], "total": int, "page": int, "page_size": int, "total_pages": int}
    """
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))
    offset = (page - 1) * page_size

    conditions = []
    params = []
    if trigger_mode:
        conditions.append("trigger_mode = ?")
        params.append(trigger_mode)
    if symbol:
        conditions.append("symbol LIKE ?")
        params.append(f"%{symbol.upper()}%")
    if direction:
        conditions.append("direction = ?")
        params.append(direction)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if confidence_min is not None:
        conditions.append("confidence >= ?")
        params.append(int(confidence_min))
    if date_start:
        conditions.append("created_at >= ?")
        params.append(f"{date_start}T00:00:00")
    if date_end:
        conditions.append("created_at <= ?")
        params.append(f"{date_end}T23:59:59")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    conn = get_conn(db_path)
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM decisions {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM decisions {where} ORDER BY decision_id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            cj = d.get("card_json")
            if cj:
                try:
                    d["card"] = json.loads(cj)
                except Exception:
                    d["card"] = None
            items.append(d)
        total_pages = (total + page_size - 1) // page_size if total else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    finally:
        conn.close()


def count_decisions_summary(db_path) -> dict:
    """决策汇总统计(顶部状态栏用)。

    返回:
        {
          "total": int,             # 决策总数
          "by_trigger": {...},      # scan/chat/tracking 各自的数量
          "open": int,              # status='open'
          "win_24h": int,           # 近 24h 内 status='win'
          "loss_24h": int,          # 近 24h 内 status='loss'
        }
    """
    from datetime import datetime, timedelta
    conn = get_conn(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        rows = conn.execute(
            "SELECT trigger_mode, COUNT(*) FROM decisions GROUP BY trigger_mode"
        ).fetchall()
        by_trigger = {r[0]: r[1] for r in rows if r[0]}
        open_n = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE status='open'"
        ).fetchone()[0]
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        win = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE status='win' AND closed_at >= ?",
            (cutoff,),
        ).fetchone()[0]
        loss = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE status='loss' AND closed_at >= ?",
            (cutoff,),
        ).fetchone()[0]
        return {
            "total": total,
            "by_trigger": by_trigger,
            "open": open_n,
            "win_24h": win,
            "loss_24h": loss,
        }
    finally:
        conn.close()
