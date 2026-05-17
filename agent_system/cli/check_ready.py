import sys
from agent_system.core.config_loader import load_config
from agent_system.data.db import get_conn, init_new_tables

def main():
    cfg = load_config("agent_system/config.yaml")
    db = cfg["data_db"]
    init_new_tables(db)  # 兜底,确保表存在
    conn = get_conn(db)
    n_exp = conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0]
    n_dec = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    n_closed = conn.execute("SELECT COUNT(*) FROM decisions WHERE status IN ('win','loss','expired')").fetchone()[0]
    conn.close()

    print(f"experiences: {n_exp}")
    print(f"decisions total: {n_dec}, closed: {n_closed}")

    enabled = cfg.get("mates", {}).get("experience", {}).get("enabled")
    if n_exp >= 30:
        if enabled:
            print("[OK] experience Mate is enabled and library is sufficient")
        else:
            print("[WARN] experiences >= 30 but mates.experience.enabled is false")
            print("       Consider setting it to true and restarting start.py")
            sys.exit(1)
    else:
        print(f"experiences below 30 ({n_exp}); keep accumulating, do not enable experience Mate yet")

if __name__ == "__main__":
    main()
