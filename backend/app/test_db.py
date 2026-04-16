import pytest
import sqlite3
from app.services import db

def test_init_db(tmp_path, mocker):
    db_path = tmp_path / "test.db"
    mocker.patch("app.services.db.DB_PATH", db_path)

    db.init_db()

    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert "lp_history" in tables
        assert "training_matches" in tables
        assert "ingestion_status" in tables

        # Test schema migration logic
        # For queue column in lp_history
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "queue" in columns

        # Test index exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = [row[0] for row in cursor.fetchall()]
        assert "idx_lp_puuid_q_ts" in indices

        # Test initial ingestion status row
        cursor = conn.execute("SELECT processed_count, total_target, is_paused FROM ingestion_status")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0] == (0, 50000, 1)

def test_init_db_migration(tmp_path, mocker):
    db_path = tmp_path / "test_migration.db"
    mocker.patch("app.services.db.DB_PATH", db_path)

    # Create legacy schema (without queue column)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE lp_history (
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
        conn.execute("INSERT INTO lp_history (puuid, tier, division, lp, wins, losses, timestamp) VALUES ('123', 'GOLD', 'I', 50, 10, 10, 123456)")

    # Run init_db which should perform migration
    db.init_db()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "queue" in columns

        # Check existing row got default value
        cursor = conn.execute("SELECT queue FROM lp_history WHERE puuid = '123'")
        assert cursor.fetchone()[0] == 'RANKED_SOLO_5x5'
