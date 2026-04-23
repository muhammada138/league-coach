"""
db.py - SQLite Persistence Layer

This service manages the internal database (league_coach.db) used for:
1. LP Trend Mapping (30-day snapshots)
2. ML Training Data (match features and outcomes)
3. Profile Caching (shared enriched responses)
4. Ingestion Worker Synchronization
"""

import asyncio
import json
import sqlite3
import time
import logging
from pathlib import Path

from ..state import DB_PATH

# --- Configuration & Setup ---

logger = logging.getLogger(__name__)

def init_db() -> None:
    """Initializes the database schema and performs required migrations."""
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
                timestamp INTEGER NOT NULL,
                queue     TEXT    NOT NULL DEFAULT 'RANKED_SOLO_5x5'
            )
        """)

        # Migration: Add 'queue' column if table existed without it
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'queue' not in columns:
            conn.execute("ALTER TABLE lp_history ADD COLUMN queue TEXT NOT NULL DEFAULT 'RANKED_SOLO_5x5'")

        # Ensure index exists
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lp_puuid_q_ts ON lp_history(puuid, queue, timestamp)"
        )

        # --- ML training data tables ---

        # Fresh clean training_matches table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS training_matches (
                match_id   TEXT    PRIMARY KEY,
                blue_feats TEXT    NOT NULL,
                red_feats  TEXT    NOT NULL,
                blue_won   INTEGER NOT NULL,
                timestamp  INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_status (
                id              INTEGER PRIMARY KEY,
                processed_count INTEGER NOT NULL DEFAULT 0,
                total_target    INTEGER NOT NULL DEFAULT 200000,
                is_paused       INTEGER NOT NULL DEFAULT 1,
                paused_at       INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Ensure singleton status row exists
        conn.execute("""
            INSERT OR IGNORE INTO ingestion_status (id, processed_count, total_target, is_paused, paused_at)
            VALUES (1, 0, 200000, 1, 0)
        """)
        # Force update old default (50k) to new target (200k)
        # This fixes the issue where existing databases were stuck on the old limit.
        conn.execute("UPDATE ingestion_status SET total_target = 200000 WHERE id = 1 AND total_target <= 50000")
        conn.commit()
        # Persistent Profile Cache (shared across all users)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enriched_profiles (
                puuid        TEXT PRIMARY KEY,
                data         TEXT,
                last_updated INTEGER
            )
        """)

        conn.commit()


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_stale_data() -> dict:
    """Standard maintenance: prune LP history older than 30 days.
    
    NOTE: Riot training matches (ingest data) are NEVER deleted by this function.
    """
    now = int(time.time())
    lp_cutoff = now - (30 * 86400)      # 30 days
    
    counts = {"lp_history": 0, "training_matches": 0}
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Only prune LP history (standard maintenance)
            res = conn.execute("DELETE FROM lp_history WHERE timestamp < ?", (lp_cutoff,))
            counts["lp_history"] = res.rowcount
            
            # NEVER delete training matches here.
            
            conn.commit()
            logger.info("Maintenance complete: pruned %d LP entries.", counts["lp_history"])
    except Exception as e:
        logger.error("Maintenance failed: %s", e)
        
    return counts

def _record_sync(puuid: str, tier: str, division: str, lp: int, wins: int, losses: int, queue: str = 'RANKED_SOLO_5x5', timestamp: int = None) -> None:
    if tier == "UNRANKED":
        return
    now = timestamp or int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT tier, division, lp, timestamp FROM lp_history "
            "WHERE puuid = ? AND queue = ? ORDER BY timestamp DESC LIMIT 1",
            (puuid, queue),
        ).fetchone()

        if row:
            last_tier, last_div, last_lp, last_ts = row
            # Skip if rank hasn't changed at all
            if last_tier == tier and last_div == division and last_lp == lp:
                return
            # Rate-limit: no more than one write per 5 minutes per player (unless timestamp is manual)
            if not timestamp and (now - last_ts) < 300:
                return

        conn.execute(
            "INSERT INTO lp_history (puuid, tier, division, lp, wins, losses, timestamp, queue) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (puuid, tier, division, lp, wins, losses, now, queue),
        )
        conn.commit()


async def record_lp_snapshot(
    puuid: str, tier: str, division: str, lp: int, wins: int, losses: int, queue: str = 'RANKED_SOLO_5x5', timestamp: int = None
) -> None:
    await asyncio.to_thread(_record_sync, puuid, tier, division, lp, wins, losses, queue, timestamp)


def _record_many_sync(snapshots: list[tuple]) -> None:
    """snapshots: list of (puuid, tier, division, lp, wins, losses, timestamp, queue)"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO lp_history (puuid, tier, division, lp, wins, losses, timestamp, queue) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            snapshots,
        )
        conn.commit()


async def record_many_lp_snapshots(snapshots: list[tuple]) -> None:
    if not snapshots: return
    await asyncio.to_thread(_record_many_sync, snapshots)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _history_sync(puuid: str, queue: str, days: int) -> list[dict]:
    since = int(time.time()) - days * 86_400
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT tier, division, lp, wins, losses, timestamp "
            "FROM lp_history "
            "WHERE puuid = ? AND queue = ? AND timestamp >= ? "
            "ORDER BY timestamp ASC",
            (puuid, queue, since),
        ).fetchall()
    return [
        {"tier": r[0], "division": r[1], "lp": r[2], "wins": r[3], "losses": r[4], "timestamp": r[5]}
        for r in rows
    ]


async def get_lp_history(puuid: str, queue: str = 'RANKED_SOLO_5x5', days: int = 30) -> list[dict]:
    return await asyncio.to_thread(_history_sync, puuid, queue, days)


def _has_history_sync(puuid: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM lp_history WHERE puuid = ? LIMIT 1",
            (puuid,),
        ).fetchone()
    return row is not None


async def has_history(puuid: str) -> bool:
    return await asyncio.to_thread(_has_history_sync, puuid)


# ---------------------------------------------------------------------------
# Ingestion status
# ---------------------------------------------------------------------------

def _get_ingestion_status_sync() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        # Migrate: ensure paused_at exists
        cursor = conn.execute("PRAGMA table_info(ingestion_status)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'paused_at' not in cols:
            conn.execute("ALTER TABLE ingestion_status ADD COLUMN paused_at INTEGER DEFAULT 0")
            conn.commit()

        row = conn.execute(
            "SELECT processed_count, total_target, is_paused, paused_at FROM ingestion_status WHERE id = 1"
        ).fetchone()
    if row is None:
        return {"processed_count": 0, "total_target": 200000, "is_paused": True, "paused_at": 0}
    return {
        "processed_count": row[0], 
        "total_target": row[1], 
        "is_paused": bool(row[2]),
        "paused_at": row[3] or 0
    }


def _toggle_ingestion_sync() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        # Migrate in-place if needed
        cursor = conn.execute("PRAGMA table_info(ingestion_status)")
        if 'paused_at' not in [r[1] for r in cursor.fetchall()]:
            conn.execute("ALTER TABLE ingestion_status ADD COLUMN paused_at INTEGER DEFAULT 0")

        # Get current state
        row = conn.execute("SELECT is_paused FROM ingestion_status WHERE id = 1").fetchone()
        was_paused = bool(row[0]) if row else True
        new_paused = 0 if was_paused else 1
        paused_at = int(time.time()) if new_paused else 0

        conn.execute(
            "UPDATE ingestion_status SET is_paused = ?, paused_at = ? WHERE id = 1",
            (new_paused, paused_at)
        )
        conn.commit()
        
        row = conn.execute(
            "SELECT processed_count, total_target, is_paused, paused_at FROM ingestion_status WHERE id = 1"
        ).fetchone()

    return {
        "processed_count": row[0], 
        "total_target": row[1], 
        "is_paused": bool(row[2]),
        "paused_at": row[3] or 0
    }


async def get_ingestion_status() -> dict:
    return await asyncio.to_thread(_get_ingestion_status_sync)


async def toggle_ingestion() -> dict:
    return await asyncio.to_thread(_toggle_ingestion_sync)


async def resume_ingestion() -> None:
    """Explicitly turn ingestion ON and clear paused_at."""
    await asyncio.to_thread(_resume_ingestion_sync)

def _resume_ingestion_sync():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE ingestion_status SET is_paused = 0, paused_at = 0 WHERE id = 1")
        conn.commit()


# ---------------------------------------------------------------------------
# Training matches
# ---------------------------------------------------------------------------

def _has_training_match_sync(match_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            "SELECT 1 FROM training_matches WHERE match_id = ?", (match_id,)
        ).fetchone() is not None


def _save_training_match_sync(
    match_id: str, blue_feats: list, red_feats: list, blue_won: bool
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        # INSERT OR IGNORE so duplicates are silently skipped
        cur = conn.execute(
            "INSERT OR IGNORE INTO training_matches (match_id, blue_feats, red_feats, blue_won, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (match_id, json.dumps(blue_feats), json.dumps(red_feats), int(blue_won), int(time.time())),
        )
        if cur.rowcount:
            # Only increment counter when a new row was actually inserted
            conn.execute(
                "UPDATE ingestion_status SET processed_count = processed_count + 1 WHERE id = 1"
            )
        conn.commit()


async def has_training_match(match_id: str) -> bool:
    return await asyncio.to_thread(_has_training_match_sync, match_id)


async def save_training_match(
    match_id: str, blue_feats: list, red_feats: list, blue_won: bool
) -> None:
    await asyncio.to_thread(_save_training_match_sync, match_id, blue_feats, red_feats, blue_won)


def get_all_training_matches_sync() -> list[dict]:
    """Return all rows from training_matches (clean data) as a list of dicts."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT blue_feats, red_feats, blue_won FROM training_matches"
        ).fetchall()
    return [{"blue_feats": row[0], "red_feats": row[1], "blue_won": row[2]} for row in rows]


def get_v1_training_matches_sync() -> list[dict]:
    """Return rows from training_matches_v1 (legacy data, form feature is leaky)."""
    with sqlite3.connect(DB_PATH) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='training_matches_v1'"
        ).fetchone()
        if not exists:
            return []
        rows = conn.execute(
            "SELECT blue_feats, red_feats, blue_won FROM training_matches_v1"
        ).fetchall()
    return [{"blue_feats": row[0], "red_feats": row[1], "blue_won": row[2]} for row in rows]

def get_enriched_profile(puuid: str) -> tuple | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT data, last_updated FROM enriched_profiles WHERE puuid = ?", (puuid,)).fetchone()
        if row:
            return json.loads(row[0]), row[1]
    return None

def save_enriched_profile(puuid: str, data: dict) -> None:
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT data FROM enriched_profiles WHERE puuid = ?", (puuid,)).fetchone()
        if row:
            try:
                existing_data = json.loads(row[0])
                existing_data.update(data)
                merged_data = json.dumps(existing_data)
            except Exception:
                merged_data = json.dumps(data)
        else:
            merged_data = json.dumps(data)
            
        conn.execute(
            "INSERT OR REPLACE INTO enriched_profiles (puuid, data, last_updated) VALUES (?, ?, ?)",
            (puuid, merged_data, now)
        )
        conn.commit()

