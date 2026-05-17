from datetime import datetime
from agent_system.data.tracking_store import get_active_tracks, save_track_snapshot

class TrackingRunner:
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
        return {
            "track_id": track.get("id"),
            "entry_price": track.get("entry_price"),
            "direction": track.get("direction"),
            "stop_loss": track.get("stop_loss"),
            "take_profit": track.get("take_profit"),
            "entry_signals": track.get("entry_signals"),
        }

    def run_once(self) -> list:
        tracks = get_active_tracks(self.db_path)
        print(f"[tracking] active tracks: {len(tracks)}")
        results = []
        for t in tracks:
            symbol = t.get("symbol")
            try:
                pack = self.build_pack(symbol, binance=self.binance, peer_symbols=["BTCUSDT"])
                pack["tracking_context"] = self._build_tracking_context(t)
                card = self.orch.run(
                    symbol=symbol, mode="tracking", data_pack=pack,
                    session_key=f"track_{t.get('id')}_{int(datetime.now().timestamp())}",
                )
                save_track_snapshot(self.db_path, t["id"],
                                     snapshot={"card": card, "price_now": pack.get("price_now")})
                results.append({"track": t, "card": card})
                if self.push:
                    self.push.push_tracking_update(t, card)
            except Exception as e:
                print(f"[tracking] {symbol} failed: {e}")
        return results
