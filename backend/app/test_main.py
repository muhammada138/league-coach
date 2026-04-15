import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_get_summoner(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    mock_riot_get.return_value = {
        "puuid": "fake-puuid",
        "gameName": "Faker",
        "tagLine": "KR1"
    }

    response = client.get("/summoner/Faker/KR1")
    assert response.status_code == 200
    assert response.json()["puuid"] == "fake-puuid"

@pytest.mark.asyncio
async def test_analyze(mocker):
    # Mock network calls
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    # For analyze, it does multiple riot_gets: one for match ids, then for each match.
    # We can just use side_effect or a mock
    async def mock_riot_get_impl(client_obj, url):
        if "ids?count=" in url:
            return ["match_1"]
        elif "/matches/" in url:
            return {
                "info": {
                    "gameDuration": 1200,
                    "participants": [
                        {
                            "puuid": "fake-puuid",
                            "championName": "Ahri",
                            "teamId": 100,
                            "win": True,
                            "teamPosition": "MIDDLE",
                            "kills": 10,
                            "deaths": 2,
                            "assists": 5,
                            "totalMinionsKilled": 150,
                            "visionScore": 20,
                            "totalDamageDealtToChampions": 15000,
                            "goldEarned": 10000,
                            "damageDealtToTurrets": 2000,
                            "wardsPlaced": 10,
                            "wardsKilled": 2,
                        }
                    ]
                }
            }
        return {}
    mock_riot_get.side_effect = mock_riot_get_impl
    
    mock_coaching = mocker.patch("app.routes.api.get_coaching_feedback")
    mock_coaching.return_value = "1. Play better.\n2. Farm more."

    response = client.get("/analyze/fake-puuid?game_name=Faker&count=5")
    assert response.status_code == 200
    assert "gameName" in response.json()

@pytest.mark.asyncio
async def test_win_predict():
    from app.services import win_predictor
    participants = [
        {"puuid": "p1", "teamId": 100, "championId": 1},
        {"puuid": "p2", "teamId": 200, "championId": 2},
    ]
    live_stats = {
        "p1": {"tier": "GOLD", "division": "I", "lp": 50, "wins": 20, "losses": 18, "avg_score": 55},
        "p2": {"tier": "SILVER", "division": "II", "lp": 10, "wins": 15, "losses": 20, "avg_score": 45},
    }
    
    # We don't need to mock the model as it falls back to a linear dot product if no model exists
    prediction = win_predictor.predict(participants, live_stats)
    assert "bluePct" in prediction
    assert "redPct" in prediction
    assert prediction["bluePct"] + prediction["redPct"] == 100

@pytest.mark.asyncio
async def test_db_lp_snapshot(mocker):
    from app.services import db
    mock_sqlite = mocker.patch("sqlite3.connect")
    # Simulate first record
    mock_sqlite.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
    
    await db.record_lp_snapshot("fake-puuid", "GOLD", "I", 50, 20, 18)
    
    # Verify execute was called
    calls = mock_sqlite.return_value.__enter__.return_value.execute.call_args_list
    assert any("INSERT INTO lp_history" in str(call) for call in calls)

def test_init_db_fresh(mocker):
    from app.services import db
    import sqlite3

    mock_db_path = mocker.MagicMock()
    mocker.patch("app.services.db.DB_PATH", mock_db_path)

    # We want a fresh in-memory db that stays alive for our checks
    mem_conn = sqlite3.connect(":memory:")

    # Mock sqlite3.connect to yield our mem_conn
    # It acts as a context manager in db.py: with sqlite3.connect(DB_PATH) as conn:
    mocker.patch("sqlite3.connect", return_value=mem_conn)

    db.init_db()

    cursor = mem_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    assert "lp_history" in tables
    assert "training_matches" in tables
    assert "ingestion_status" in tables

    # Check lp_history has 'queue' column
    cursor.execute("PRAGMA table_info(lp_history)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "queue" in columns

def test_init_db_migration(mocker):
    from app.services import db
    import sqlite3

    mock_db_path = mocker.MagicMock()
    mocker.patch("app.services.db.DB_PATH", mock_db_path)

    # Pre-populate an in-memory DB with old schema
    mem_conn = sqlite3.connect(":memory:")
    mem_conn.execute("""
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
    mem_conn.commit()

    mocker.patch("sqlite3.connect", return_value=mem_conn)

    db.init_db()

    cursor = mem_conn.cursor()
    cursor.execute("PRAGMA table_info(lp_history)")
    columns = [row[1] for row in cursor.fetchall()]

    # The migration should have added 'queue'
    assert "queue" in columns
