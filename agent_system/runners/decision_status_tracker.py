from datetime import datetime, timedelta
from agent_system.data.decisions_store import list_open_decisions, update_decision_status

class DecisionStatusTracker:
    def __init__(self, db_path: str, binance, expire_days: int = 7):
        self.db_path = db_path
        self.binance = binance
        self.expire_days = expire_days

    def _highest_low(self, symbol: str):
        klines = self.binance.get_klines(symbol, interval="1h", limit=200)
        if not klines:
            return None, None, None
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        last_close = float(klines[-1][4])
        return max(highs), min(lows), last_close

    def _evaluate(self, decision: dict):
        direction = decision.get("direction")
        if direction not in ("多", "空"):
            return None
        entry = decision.get("entry_price")
        sl = decision.get("stop_loss")
        tp = decision.get("take_profit")
        if entry is None or sl is None or tp is None:
            return None
        symbol = decision["symbol"]
        try:
            highest, lowest, last_close = self._highest_low(symbol)
        except Exception:
            return None
        if highest is None:
            return None
        if direction == "多":
            if lowest <= sl:
                pnl_pct = (sl - entry) / entry * 100
                return ("loss", pnl_pct)
            if highest >= tp:
                pnl_pct = (tp - entry) / entry * 100
                return ("win", pnl_pct)
        else:
            if highest >= sl:
                pnl_pct = (entry - sl) / entry * 100
                return ("loss", pnl_pct)
            if lowest <= tp:
                pnl_pct = (entry - tp) / entry * 100
                return ("win", pnl_pct)
        created = datetime.fromisoformat(decision["created_at"])
        if datetime.now() - created > timedelta(days=self.expire_days):
            if direction == "多":
                pnl_pct = (last_close - entry) / entry * 100
            else:
                pnl_pct = (entry - last_close) / entry * 100
            return ("expired", pnl_pct)
        return None

    def run_once(self):
        opens = list_open_decisions(self.db_path)
        for d in opens:
            result = self._evaluate(d)
            if result:
                status, pnl = result
                update_decision_status(self.db_path, d["decision_id"], status=status, realized_pnl_pct=pnl)
