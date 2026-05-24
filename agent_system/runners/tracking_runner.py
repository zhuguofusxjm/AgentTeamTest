"""持仓跟踪 Runner — 对已开的仓位定时重新评估,触发出场建议。

每小时跑一次(start.py 的 tracking_loop)。和 scan 不同的是:
- scan: 全市场挑候选,产新决策
- tracking: 已有仓位的回看,产出场建议(仍走 lean 模式但 mode='tracking')

跟踪上下文(tracking_context)会塞进 DataPack,
让分析师知道"这是一个已经开了 X 天的仓位,入场价 Y、SL Z",
而不是当作新决策处理。
"""
from datetime import datetime
from agent_system.data.tracking_store import get_active_tracks, save_track_snapshot

class TrackingRunner:
    """对所有 active 跟踪记录跑一次评估,产快照入库 + 推送。"""

    def __init__(self, cfg, llm_client, orchestrator, binance, db_path, data_packer,
                 push_client=None):
        self.cfg = cfg
        self.llm = llm_client
        self.orch = orchestrator
        self.binance = binance
        self.db_path = db_path
        self.build_pack = data_packer
        self.push = push_client

    def _build_tracking_context(self, track: dict) -> dict:
        """从跟踪记录里抽出关键字段,塞进 DataPack 给 mate 看。

        告诉分析师当前仓位的入场价 / SL / TP / 入场理由,
        他们才能给出"该不该出场""SL 要不要上移"这类判断。
        """
        return {
            "track_id": track.get("id"),
            "entry_price": track.get("entry_price"),
            "direction": track.get("direction"),
            "stop_loss": track.get("stop_loss"),
            "take_profit": track.get("take_profit"),
            "entry_signals": track.get("entry_signals"),
        }

    def run_once(self) -> list:
        """跑一轮:逐个 active 跟踪 → 跑 tracking 模式圆桌 → 入库 + push。

        单个失败被吞,不影响其他。
        """
        tracks = get_active_tracks(self.db_path)
        print(f"[tracking] active tracks: {len(tracks)}")
        results = []
        for t in tracks:
            symbol = t.get("symbol")
            try:
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                # 把跟踪上下文挂在 pack 上,mate 能看到当前仓位状况
                pack["tracking_context"] = self._build_tracking_context(t)
                # session_key 用 track_id + 时间戳,方便审计文件名识别
                card = self.orch.run(
                    symbol=symbol, mode="tracking", data_pack=pack,
                    session_key=f"track_{t.get('id')}_{int(datetime.now().timestamp())}",
                )
                # 落盘快照(每次跟踪的决策卡片 + 当时的价格)
                save_track_snapshot(self.db_path, t["id"],
                                     snapshot={"card": card, "price_now": pack.get("price_now")})
                results.append({"track": t, "card": card})
                if self.push:
                    self.push.push_tracking_update(t, card)
            except Exception as e:
                print(f"[tracking] {symbol} failed: {e}")
        return results
