import sqlite3
import pytest
from app.services import db

def test_init_db(tmp_path, mocker):
    test_db_path = tmp_path / "test.db"
    mocker.patch("app.services.db.DB_PATH", test_db_path)

    # Call the function being tested
    db.init_db()

    # Connect to the database and verify tables
    with sqlite3.connect(test_db_path) as conn:
        # Verify lp_history table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lp_history'")
        assert cursor.fetchone() is not None

        # Verify training_matches table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='training_matches'")
        assert cursor.fetchone() is not None

        # Verify ingestion_status table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ingestion_status'")
        assert cursor.fetchone() is not None

        # Verify idx_lp_puuid_q_ts index exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_lp_puuid_q_ts'")
        assert cursor.fetchone() is not None

        # Verify singleton row in ingestion_status
        cursor = conn.execute("SELECT id, processed_count, total_target, is_paused FROM ingestion_status WHERE id=1")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == 0
        assert row[2] == 50000
        assert row[3] == 1


def test_init_db_migration(tmp_path, mocker):
    test_db_path = tmp_path / "test.db"
    mocker.patch("app.services.db.DB_PATH", test_db_path)

    # Create the table without the 'queue' column
    with sqlite3.connect(test_db_path) as conn:
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
        conn.commit()

    # Call init_db to trigger the migration
    db.init_db()

    # Verify the 'queue' column was added
    with sqlite3.connect(test_db_path) as conn:
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = [row[1] for row in cursor.fetchall()]
        assert 'queue' in columns
