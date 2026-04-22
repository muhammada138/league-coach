import pytest
import sqlite3
from pathlib import Path
from app.services.ingestion import _rank_cache
from app.services import db

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, mocker):
    # Mock DB_PATH to a temporary location for every test
    temp_db = tmp_path / "test_league_coach.db"
    mocker.patch("app.services.db.DB_PATH", temp_db)
    # Ensure schema is created
    db.init_db()
    
    yield
    
    # Optionally clear rank cache too
    _rank_cache.clear()
