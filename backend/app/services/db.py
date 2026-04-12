"""
SQLite service for persisting LP snapshots over time.

Every time a player profile is viewed, the current LP / tier / division is
written to lp_history (at most once per 5 minutes per player, and only when
the rank has actually changed since the last snapshot).  This builds up a
real 30-day LP history without any third-party data source.
"""

import asyncio
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "league_coach.db"

# ---------------------------------------------------------------------------
# Schema init  (called once at startup)
# ---------------------------------------------------------------------------

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lp_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                puuid     TEXT    NOT NULL,
                tier      TEXT    NOT NULL,
                division  TEXT    NOT NULL,
                lp        INTEGER NOT NULL,
                wins      INTEGER NOT NULL,
                losses    INTEGER NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lp_puuid_ts ON lp_history(puuid, timestamp)"
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def _record_sync(puuid: str, tier: str, division: str, lp: int, wins: int, losses: int) -> None:
    if tier == "UNRANKED":
        return
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT tier, division, lp, timestamp FROM lp_history "
            "WHERE puuid = ? ORDER BY timestamp DESC LIMIT 1",
            (puuid,),
        ).fetchone()

        if row:
            last_tier, last_div, last_lp, last_ts = row
            # Skip if rank hasn't changed at all
            if last_tier == tier and last_div == division and last_lp == lp:
                return
            # Rate-limit: no more than one write per 5 minutes per player
            if (now - last_ts) < 300:
                return

        conn.execute(
            "INSERT INTO lp_history (puuid, tier, division, lp, wins, losses, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (puuid, tier, division, lp, wins, losses, now),
        )
        conn.commit()


async def record_lp_snapshot(
    puuid: str, tier: str, division: str, lp: int, wins: int, losses: int
) -> None:
    await asyncio.to_thread(_record_sync, puuid, tier, division, lp, wins, losses)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _history_sync(puuid: str, days: int) -> list[dict]:
    since = int(time.time()) - days * 86_400
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT tier, division, lp, wins, losses, timestamp "
            "FROM lp_history "
            "WHERE puuid = ? AND timestamp >= ? "
            "ORDER BY timestamp ASC",
            (puuid, since),
        ).fetchall()
    return [
        {"tier": r[0], "division": r[1], "lp": r[2], "wins": r[3], "losses": r[4], "timestamp": r[5]}
        for r in rows
    ]


async def get_lp_history(puuid: str, days: int = 30) -> list[dict]:
    return await asyncio.to_thread(_history_sync, puuid, days)
