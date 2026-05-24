"""决策状态追踪器 — 定时检查 open 决策有无触发 SL/TP/超时。

每小时跑一次(start.py 的 status_loop)。流程:
  1. 从 SQL 读所有 status='open' 的决策
  2. 对每个决策,从入场时刻起拉 1h K 线,看历史高低有没有触发 SL/TP
  3. 触发 → 标记 win/loss + 记录 pnl_pct
  4. 没触发但超过 expire_days(默认 7 天) → 标记 expired

被标记的决策才会进入复盘官的归因池(retrospective_runner)。
"""
from datetime import datetime, timedelta
from agent_system.data.decisions_store import list_open_decisions, update_decision_status

class DecisionStatusTracker:
    """检查 open 决策的触发情况(win/loss/expired)。

    expire_days: 决策有效期。超过这个时长没触发 SL/TP 就标 expired,
    用最新 close 价计算 pnl(可能是正可能是负,取决于持仓方向)。
    """

    def __init__(self, db_path: str, binance, expire_days: int = 7):
        self.db_path = db_path
        self.binance = binance
        self.expire_days = expire_days

    def _highest_low(self, symbol: str, start_ms: int):
        """从 start_ms 开始拉 1h K 线,返回原始 K 线列表(用于逐根遍历)。"""
        klines = self.binance.get_klines(symbol, interval="1h", limit=500, start_time=start_ms)
        return klines or []

    def _evaluate(self, decision: dict):
        """单个决策的触发判定——逐根 K 线遍历,先触发者为准。

        逐根扫描:
        - 多头:某根 low <= SL → loss;某根 high >= TP → win
        - 空头:某根 high >= SL → loss;某根 low <= TP → win
        同一根 K 线内 SL 和 TP 都被触发时,保守判 loss(无法确定先后)。
        全部扫完都没触发 → 检查是否超时。
        """
        direction = decision.get("direction")
        if direction not in ("多", "空"):
            return None
        entry = decision.get("entry_price")
        sl = decision.get("stop_loss")
        tp = decision.get("take_profit")
        if entry is None or sl is None or tp is None:
            return None
        symbol = decision["symbol"]
        created = datetime.fromisoformat(decision["created_at"])
        start_ms = int(created.timestamp() * 1000)
        try:
            klines = self._highest_low(symbol, start_ms)
        except Exception:
            return None
        if not klines:
            return None

        # 逐根遍历,找第一根触发 SL 或 TP 的 K 线
        for k in klines:
            high = float(k[2])
            low = float(k[3])
            if direction == "多":
                hit_sl = low <= sl
                hit_tp = high >= tp
            else:
                hit_sl = high >= sl
                hit_tp = low <= tp

            if hit_sl and hit_tp:
                # 同一根内两者都触发,保守判 loss(无法确定 tick 级先后)
                if direction == "多":
                    pnl_pct = (sl - entry) / entry * 100
                else:
                    pnl_pct = (entry - sl) / entry * 100
                return ("loss", pnl_pct)
            if hit_sl:
                if direction == "多":
                    pnl_pct = (sl - entry) / entry * 100
                else:
                    pnl_pct = (entry - sl) / entry * 100
                return ("loss", pnl_pct)
            if hit_tp:
                if direction == "多":
                    pnl_pct = (tp - entry) / entry * 100
                else:
                    pnl_pct = (entry - tp) / entry * 100
                return ("win", pnl_pct)

        # 全部 K 线都没触发,检查是否超时
        last_close = float(klines[-1][4])
        if datetime.now() - created > timedelta(days=self.expire_days):
            if direction == "多":
                pnl_pct = (last_close - entry) / entry * 100
            else:
                pnl_pct = (entry - last_close) / entry * 100
            return ("expired", pnl_pct)
        return None

    def run_once(self):
        """单次扫描所有 open 决策,触发的写回数据库。"""
        opens = list_open_decisions(self.db_path)
        for d in opens:
            result = self._evaluate(d)
            if result:
                status, pnl = result
                update_decision_status(self.db_path, d["decision_id"], status=status, realized_pnl_pct=pnl)
