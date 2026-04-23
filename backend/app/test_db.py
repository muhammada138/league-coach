import sqlite3
import pytest
from pathlib import Path
from app.services import db

def test_init_db(tmp_path, mocker):
    temp_db_path = tmp_path / "data" / "test_league_coach.db"
    mocker.patch("app.services.db.DB_PATH", temp_db_path)

    # Call init_db - this should create the parent directory and initialize the database
    db.init_db()

    assert temp_db_path.parent.exists()
    assert temp_db_path.exists()

    with sqlite3.connect(temp_db_path) as conn:
        # Check lp_history table
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert "id" in columns
        assert "puuid" in columns
        assert "queue" in columns
        assert columns["queue"] == "TEXT"

        # Check lp_history index
        cursor = conn.execute("PRAGMA index_list(lp_history)")
        indexes = [row[1] for row in cursor.fetchall()]
        assert "idx_lp_puuid_q_ts" in indexes

        # Check training_matches table
        cursor = conn.execute("PRAGMA table_info(training_matches)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "match_id" in columns

        # Check ingestion_status table
        cursor = conn.execute("PRAGMA table_info(ingestion_status)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "id" in columns

        # Check ingestion_status singleton row
        row = conn.execute("SELECT processed_count, total_target, is_paused FROM ingestion_status WHERE id = 1").fetchone()
        assert row is not None
        assert row == (0, 200000, 1)

def test_init_db_migration(tmp_path, mocker):
    temp_db_path = tmp_path / "migration_test.db"
    mocker.patch("app.services.db.DB_PATH", temp_db_path)

    # Pre-create the database with the old schema (missing 'queue' column)
    with sqlite3.connect(temp_db_path) as conn:
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

    # Call init_db which should trigger the migration
    db.init_db()

    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = {row[1]: row[4] for row in cursor.fetchall()}
        assert "queue" in columns
        # Check that default value is set to 'RANKED_SOLO_5x5'
        # PRAGMA table_info returns default value in column 4 (dflt_value)
        assert columns["queue"] == "'RANKED_SOLO_5x5'"
