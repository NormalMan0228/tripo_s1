"""Create or update operator (admin) accounts directly in a server database.

Admins get a large Starseed and Leaf coin balance and unlock the in-game debug
tools. The password comes from the TRIPOTHON_ADMIN_PASSWORD environment variable
so it never lands in shell history, the repository or logs. Operator accounts
skip the player password rule (uppercase + special character) on purpose.

    set TRIPOTHON_ADMIN_PASSWORD=...
    python tools/admin_accounts.py --data-dir <server-data> polytech1 polytech2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

from argon2 import PasswordHasher

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import homestead  # noqa: E402
from server.database import Database  # noqa: E402

STARSEEDS = 100000
LEAF_COINS = 10000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--mode", default="demo", choices=["demo", "live"])
    parser.add_argument("usernames", nargs="+")
    args = parser.parse_args()
    password = os.environ.get("TRIPOTHON_ADMIN_PASSWORD", "")
    if len(password) < 10:
        raise SystemExit("Set TRIPOTHON_ADMIN_PASSWORD (10+ characters).")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(args.data_dir / "world.sqlite3", args.mode)
    hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
    now = time.time()
    with db.transaction() as conn:
        for name in args.usernames:
            name = name.lower()
            row = conn.execute("SELECT id,shards FROM users WHERE username=?", (name,)).fetchone()
            if row:
                user_id = row["id"]
                conn.execute("UPDATE users SET password_hash=?,role='admin' WHERE id=?", (hasher.hash(password), user_id))
                top_up = max(0, STARSEEDS - row["shards"])
            else:
                user_id = str(uuid.uuid4())
                conn.execute("INSERT INTO users(id,username,password_hash,shards,created,role) VALUES (?,?,?,?,?,'admin')",
                             (user_id, name, hasher.hash(password), 0, now))
                conn.execute("INSERT INTO objects(id,owner_id,creator_id,asset_id,name,created) VALUES (?,?,?,?,?,?)",
                             (str(uuid.uuid4()), user_id, user_id, "starter", "환영의 나무 의자", now))
                top_up = STARSEEDS
            if top_up:
                conn.execute("INSERT INTO ledger VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), user_id, top_up, "admin_seed", user_id, now))
                conn.execute("UPDATE users SET shards=shards+? WHERE id=?", (top_up, user_id))
            state_row = conn.execute("SELECT state FROM homesteads WHERE user_id=?", (user_id,)).fetchone()
            state = json.loads(state_row["state"]) if state_row else homestead.initial()
            state["coins"] = max(state.get("coins", 0), LEAF_COINS)
            state["version"] = state.get("version", 0) + 1
            conn.execute("INSERT INTO homesteads VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state",
                         (user_id, json.dumps(state)))
            print(f"admin ready: {name}")


if __name__ == "__main__":
    main()
