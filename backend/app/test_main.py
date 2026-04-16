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
async def test_get_history(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    async def mock_riot_get_impl(client_obj, url):
        if "ids?" in url:
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

    response = client.get("/history/fake-puuid")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["matchId"] == "match_1"
    assert data[0]["championName"] == "Ahri"

def test_lp_history(mocker):
    mock_db_get_lp_history = mocker.patch("app.routes.api.db.get_lp_history")

    # Mock return value since get_lp_history is async we need to use AsyncMock or mock return value coroutine.
    # Actually mocker.patch handles coroutine return_value with AsyncMock by default in recent versions, but wait!
    # db.get_lp_history is an async function. Let's make sure it returns a coroutine.
    async def mock_get(*args, **kwargs):
        return [
            {"tier": "GOLD", "division": "I", "lp": 50, "wins": 20, "losses": 18, "timestamp": 1234567890}
        ]
    mock_db_get_lp_history.side_effect = mock_get

    # Test default queue
    response = client.get("/lp-history/fake-puuid")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tier"] == "GOLD"
    assert data[0]["lp"] == 50
    mock_db_get_lp_history.assert_called_with("fake-puuid", queue="RANKED_SOLO_5x5", days=30)

    # Test custom queue
    response = client.get("/lp-history/fake-puuid?queue=RANKED_FLEX_SR")
    assert response.status_code == 200
    mock_db_get_lp_history.assert_called_with("fake-puuid", queue="RANKED_FLEX_SR", days=30)

@pytest.mark.asyncio
async def test_get_history_invalid_params():
    # Test invalid count parameter
    response = client.get("/history/fake-puuid?count=invalid")
    assert response.status_code == 422

    # Test invalid start parameter
    response = client.get("/history/fake-puuid?start=invalid")
    assert response.status_code == 422

    # Test invalid queue parameter
    response = client.get("/history/fake-puuid?queue=invalid")
    assert response.status_code == 422

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

@pytest.mark.asyncio
async def test_get_cached_rank(mocker):
    from app.services.riot import get_cached_rank
    from app.state import rank_cache
    import httpx

    # Clear the cache before tests
    rank_cache.cache.clear()

    # 1. Test missing puuid
    rank = await get_cached_rank(None, "")
    assert rank == "Unranked"

    # 2. Test cache miss (calls API)
    # Since riot_get is called with client, we can mock the httpx.AsyncClient
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I"},
        {"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "IV"}
    ]
    mock_client.get.return_value = mock_response

    rank = await get_cached_rank(mock_client, "puuid-123", "na1")
    assert rank == "Gold IV"
    # Ensure it's in cache
    assert "puuid-123" in rank_cache

    # 3. Test cache hit (doesn't call API again)
    mock_client.get.reset_mock()
    rank = await get_cached_rank(mock_client, "puuid-123", "na1")
    assert rank == "Gold IV"
    mock_client.get.assert_not_called()

    # 4. Test missing RANKED_SOLO_5x5
    mock_response2 = mocker.Mock()
    mock_response2.status_code = 200
    mock_response2.json.return_value = [
        {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I"}
    ]
    mock_client.get.return_value = mock_response2

    rank = await get_cached_rank(mock_client, "puuid-456", "na1")
    assert rank == "Unranked"
    assert rank_cache["puuid-456"] == "Unranked"

    # 5. Test API failure/exception
    mock_client.get.side_effect = Exception("API Error")

    rank = await get_cached_rank(mock_client, "puuid-789", "na1")
    assert rank == "Unranked"
    # Should not cache Unranked on failure
    assert "puuid-789" not in rank_cache
