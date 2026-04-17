import pytest
from fastapi.testclient import TestClient
import asyncio
from app.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Rift IQ Backend"}

@pytest.mark.asyncio
async def test_get_summoner_mock(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.return_value = {"puuid": "mock-puuid", "gameName": "MockPlayer", "tagLine": "NA1"}
    
    response = client.get("/summoner/MockPlayer/NA1?region=na1")
    assert response.status_code == 200
    data = response.json()
    assert data["puuid"] == "mock-puuid"
    assert data["gameName"] == "MockPlayer"

@pytest.mark.asyncio
async def test_get_profile_mock(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        {"summonerLevel": 100, "profileIconId": 1}, # summoner
        [{"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "I", "leaguePoints": 50, "wins": 10, "losses": 5}] # entries
    ]
    mocker.patch("app.routes.api.db.record_lp_snapshot", new_callable=mocker.AsyncMock)
    mocker.patch("app.routes.api.backfill_if_needed", new_callable=mocker.AsyncMock)

    response = client.get("/profile/mock-puuid?region=na1")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "GOLD"
    assert data["summonerLevel"] == 100

@pytest.mark.asyncio
async def test_analyze_summoner_mock(mocker):
    mock_fetch = mocker.patch("app.routes.api._fetch_recent_matches", new_callable=mocker.AsyncMock)
    mock_fetch.return_value = (["m1"], 420, [{"info": {"gameDuration": 1500, "participants": [{"puuid": "p1", "win": True}]}}])
    
    mocker.patch("app.routes.api._process_match", return_value={
        "matchId": "m1",
        "gameEndTimestamp": 123456789,
        "win": True, "score": 70, "position": "MID", "kda": 3.0, "cspm": 8.0, 
        "playerCspm": 8.0,
        "diffedLane": "MIDDLE",
        "playerStats": {
            "win": True, "gameDuration": 1500, "kills": 5, "deaths": 1, "assists": 10, 
            "totalMinionsKilled": 200, "teamPosition": "MIDDLE", "championName": "Lux",
            "visionScore": 20, "totalDamageDealtToChampions": 15000, "goldEarned": 10000,
            "damageDealtToTurrets": 2000, "wardsPlaced": 10, "wardsKilled": 5
        },
        "lobbyAverages": {
            "kills": 5, "deaths": 5, "assists": 10, "totalMinionsKilled": 200,
            "visionScore": 20, "totalDamageDealtToChampions": 15000, "goldEarned": 10000,
            "damageDealtToTurrets": 2000, "wardsPlaced": 10, "wardsKilled": 5
        },
        "stats": {}
    })
    mocker.patch("app.routes.api._generate_coaching", new_callable=mocker.AsyncMock, return_value="Good job.")
    
    response = client.get("/analyze/p1?game_name=P1&count=1&region=na1")
    assert response.status_code == 200
    data = response.json()
    assert data["winRate"] == 100.0

@pytest.mark.asyncio
async def test_get_history_mock(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["m1"], # match IDs
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "p1", "win": True, "championName": "Lux", "kills": 5, "deaths": 1, "assists": 10, "visionScore": 20}]}} # match detail
    ]
    mocker.patch("app.routes.api._compute_perf_score", return_value=80.0)
    mocker.patch("app.routes.api._compute_diffed_lane", return_value="MIDDLE")

    response = client.get("/history/p1?start=0&count=1&region=na1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["championName"] == "Lux"

@pytest.mark.asyncio
async def test_get_live_game_mock(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.return_value = {
        "gameId": 123, "gameMode": "CLASSIC", "gameLength": 100, "gameQueueConfigId": 420,
        "participants": [{"puuid": "p1", "championId": 1, "teamId": 100}]
    }
    mocker.patch("app.services.role_identifier.assign_team_roles", new_callable=mocker.AsyncMock, return_value={1: "MIDDLE"})

    response = client.get("/live/p1?region=na1")
    assert response.status_code == 200
    data = response.json()
    assert data["inGame"] is True
    assert data["participants"][0]["assignedPosition"] == "MIDDLE"

@pytest.mark.asyncio
async def test_live_enrich_mock(mocker):
    # This is complex to mock fully, but we can verify the structure
    mock_riot_get = mocker.patch("app.routes.api.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        [], # entries
        ["m1"], # match IDs
    ]
    mocker.patch("app.routes.api.get_match_details", new_callable=mocker.AsyncMock, return_value={
        "metadata": {"matchId": "m1"},
        "info": {"gameDuration": 1200, "participants": [{"puuid": "p1", "win": True, "championId": 1}]}
    })
    mocker.patch("app.routes.api._compute_perf_score", return_value=75.0)

    payload = {"puuids": ["p1"], "queue_id": 420}
    response = client.post("/live-enrich", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "p1" in data

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

    # Use await because predict is now async
    prediction = await win_predictor.predict(participants, live_stats)
    assert "bluePct" in prediction
    assert "redPct" in prediction

def test_win_predict_empty_participants():
    from app.services import win_predictor
    import pytest
    
    @pytest.mark.asyncio
    async def run_test():
        prediction = await win_predictor.predict([], {})
        assert "error" in prediction
    
    asyncio.run(run_test())

@pytest.mark.asyncio
async def test_ask_coach_mock(mocker):
    mock_ask = mocker.patch("app.routes.api.ask_coach_question", new_callable=mocker.AsyncMock)
    mock_ask.return_value = "Keep farming."

    payload = {"question": "How do I win?", "context": "Player is 0/10."}
    response = client.post("/ask", json=payload)
    assert response.status_code == 200
    assert response.json()["answer"] == "Keep farming."
