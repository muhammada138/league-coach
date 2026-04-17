import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_get_summoner_happy_path(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    mock_riot_get.return_value = {
        "puuid": "fake-puuid",
        "gameName": "Faker",
        "tagLine": "KR1"
    }

    response = client.get("/summoner/Faker/KR1")
    assert response.status_code == 200
    assert response.json() == {
        "puuid": "fake-puuid",
        "gameName": "Faker",
        "tagLine": "KR1"
    }

    # Assert correct URL was called. Default region maps to "americas" or similar.
    # By default RIOT_REGION might be na1, making routing "americas".
    # Just checking the URL string construction logic.
    call_args = mock_riot_get.call_args[0]
    assert "api.riotgames.com/riot/account/v1/accounts/by-riot-id/Faker/KR1" in call_args[1]

@pytest.mark.asyncio
async def test_get_summoner_custom_region(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    mock_riot_get.return_value = {
        "puuid": "fake-puuid",
        "gameName": "Faker",
        "tagLine": "KR1"
    }

    response = client.get("/summoner/Faker/KR1?region=eun1")
    assert response.status_code == 200

    # "eun1" maps to "europe" in get_routing
    call_args = mock_riot_get.call_args[0]
    assert "https://europe.api.riotgames.com" in call_args[1]

@pytest.mark.asyncio
async def test_get_summoner_not_found(mocker):
    from fastapi import HTTPException
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    mock_riot_get.side_effect = HTTPException(status_code=404, detail="Not Found")

    response = client.get("/summoner/Unknown/000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"

@pytest.mark.asyncio
async def test_analyze(mocker):
    # Mock network calls
    mock_riot_get = mocker.patch("app.routes.api_helpers.riot_get")
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

    mocker.patch("app.routes.api_helpers.get_coaching_feedback", return_value="1. Play better.\n2. Farm more.")

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
async def test_get_history_missing_path_param():
    # Test missing puuid path parameter
    response = client.get("/history/")
    assert response.status_code == 404

@pytest.fixture(autouse=True)
def clear_caches():
    from app.state import route_cache
    route_cache.cache.clear()
    yield

@pytest.mark.asyncio
async def test_get_history_empty_matches(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    mock_riot_get.return_value = []

    response = client.get("/history/fake-puuid-empty")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_get_history_exceptions(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    async def mock_riot_get_impl(client_obj, url):
        if "ids?" in url:
            return ["match_1", "match_2"]
        elif "match_1" in url:
            return {
                "info": {
                    "gameDuration": 1200,
                    "participants": [{"puuid": "fake-puuid-exception", "championName": "Ahri", "teamId": 100, "win": True, "kills": 10, "deaths": 2, "assists": 5, "visionScore": 20}]
                }
            }
        elif "match_2" in url:
            raise Exception("API failure")
        return {}
    mock_riot_get.side_effect = mock_riot_get_impl

    response = client.get("/history/fake-puuid-exception")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["matchId"] == "match_1"

@pytest.mark.asyncio
async def test_get_history_player_not_found(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    async def mock_riot_get_impl(client_obj, url):
        if "ids?" in url:
            return ["match_1"]
        elif "/matches/" in url:
            return {
                "info": {
                    "gameDuration": 1200,
                    "participants": [{"puuid": "other-puuid", "championName": "Ahri", "teamId": 100, "win": True, "kills": 1, "deaths": 1, "assists": 1, "visionScore": 1}]
                }
            }
        return {}
    mock_riot_get.side_effect = mock_riot_get_impl

    response = client.get("/history/fake-puuid-notfound")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_get_history_count_clamping(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    async def mock_riot_get_impl(client_obj, url):
        if "ids?" in url:
            # Check if count=10 is in the url despite count=20 in the request
            assert "count=10" in url
            return []
        return {}
    mock_riot_get.side_effect = mock_riot_get_impl

    response = client.get("/history/fake-puuid-clamping?count=20")
    assert response.status_code == 200
    assert response.json() == []

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

def test_win_predict_empty_participants():
    from app.services import win_predictor
    prediction = win_predictor.predict([], {})
    assert "error" in prediction
    assert prediction["error"] == "No participants provided."

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

@pytest.mark.asyncio
async def test_get_match_timeline(mocker):
    from app.services.riot import get_match_timeline
    from app.state import timeline_cache
    import httpx

    # Clear the cache before tests
    timeline_cache.cache.clear()

    # 1. Test cache miss (calls API)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"info": {"frames": []}}
    mock_client.get.return_value = mock_response

    timeline = await get_match_timeline(mock_client, "match-123", "americas")
    assert timeline == {"info": {"frames": []}}
    # Ensure it's in cache
    assert "match-123" in timeline_cache

    # 2. Test cache hit (doesn't call API again)
    mock_client.get.reset_mock()
    timeline = await get_match_timeline(mock_client, "match-123", "americas")
    assert timeline == {"info": {"frames": []}}
    mock_client.get.assert_not_called()

    # 3. Test API failure/exception
    # Use a generic Exception to simulate a network issue or missing error path coverage
    # and to ensure the broader except Exception block works as expected.
    mock_client.get.side_effect = Exception("API Error")

    timeline = await get_match_timeline(mock_client, "match-456", "americas")
    assert timeline is None
    # Should not cache None on failure
    assert "match-456" not in timeline_cache
