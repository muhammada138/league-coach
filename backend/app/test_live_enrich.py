import pytest
from fastapi.testclient import TestClient
from app.main import app
import asyncio

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_caches():
    from app.state import enriched_cache
    enriched_cache.cache.clear()
    yield

@pytest.mark.asyncio
async def test_live_enrich_duo_detection(mocker):
    # Mock riot_get to simulate match history for two players
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    
    p1_puuid = "p1-puuid"
    p2_puuid = "p2-puuid"
    
    # Shared matches
    m1 = "match-1"
    m2 = "match-2"
    m3 = "match-3"
    
    async def mock_riot_get_impl(client_obj, url):
        # League entries
        if "/league/v4/entries/by-puuid/" in url:
            return []
        
        # Match IDs
        if f"/match/v5/matches/by-puuid/{p1_puuid}/ids" in url:
            return [m1, m2, m3]
        if f"/match/v5/matches/by-puuid/{p2_puuid}/ids" in url:
            return [m1, m2, m3]
        
        # Match Details
        if f"/match/v5/matches/{m1}" in url:
            return {
                "metadata": {"matchId": m1},
                "info": {
                    "gameDuration": 1200,
                    "participants": [
                        {"puuid": p1_puuid, "win": True, "championId": 1, "teamPosition": "TOP"},
                        {"puuid": p2_puuid, "win": True, "championId": 2, "teamPosition": "JUNGLE"}
                    ]
                }
            }
        if f"/match/v5/matches/{m2}" in url:
            return {
                "metadata": {"matchId": m2},
                "info": {
                    "gameDuration": 1200,
                    "participants": [
                        {"puuid": p1_puuid, "win": True, "championId": 1, "teamPosition": "TOP"},
                        {"puuid": p2_puuid, "win": True, "championId": 2, "teamPosition": "JUNGLE"}
                    ]
                }
            }
        if f"/match/v5/matches/{m3}" in url:
            return {
                "metadata": {"matchId": m3},
                "info": {
                    "gameDuration": 1200,
                    "participants": [
                        {"puuid": p1_puuid, "win": True, "championId": 1, "teamPosition": "TOP"},
                        {"puuid": p2_puuid, "win": True, "championId": 2, "teamPosition": "JUNGLE"}
                    ]
                }
            }
        return {}

    mock_riot_get.side_effect = mock_riot_get_impl
    
    # Mock compute_perf_score
    mocker.patch("app.routes.api._compute_perf_score", return_value=75.0)

    payload = {
        "puuids": [p1_puuid, p2_puuid],
        "queue_id": 420
    }
    
    response = client.post("/live-enrich", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert p1_puuid in data
    assert p2_puuid in data
    
    # Both should be in the same duo group
    assert data[p1_puuid]["duo_group"] != 0
    assert data[p1_puuid]["duo_group"] == data[p2_puuid]["duo_group"]
    
    # Check shared stats (3 wins out of 3 games = 100% WR)
    assert data[p1_puuid]["duo_wr"] == 100.0
    assert data[p1_puuid]["duo_label"] == "Terror Duo"

@pytest.mark.asyncio
async def test_live_enrich_synergy_found(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    p1_puuid = "p1-puuid"
    p2_puuid = "p2-puuid"
    m1, m2, m3, m4, m5 = "m1", "m2", "m3", "m4", "m5"
    
    async def mock_riot_get_impl(client_obj, url):
        if "/league/v4/entries/by-puuid/" in url: return []
        if f"/match/v5/matches/by-puuid/{p1_puuid}/ids" in url: return [m1, m2, m3, m4, m5]
        if f"/match/v5/matches/by-puuid/{p2_puuid}/ids" in url: return [m1, m2, m3, m4, m5]
        
        # 3 wins out of 5 games = 60% WR -> Synergy Found
        wins = {m1: True, m2: True, m3: True, m4: False, m5: False}
        mid = url.split("/")[-1]
        return {
            "metadata": {"matchId": mid},
            "info": {
                "gameDuration": 1200,
                "participants": [
                    {"puuid": p1_puuid, "win": wins.get(mid, False), "championId": 1},
                    {"puuid": p2_puuid, "win": wins.get(mid, False), "championId": 2}
                ]
            }
        }

    mock_riot_get.side_effect = mock_riot_get_impl
    mocker.patch("app.routes.api._compute_perf_score", return_value=75.0)

    payload = {"puuids": [p1_puuid, p2_puuid], "queue_id": 420}
    response = client.post("/live-enrich", json=payload)
    data = response.json()
    
    assert data[p1_puuid]["duo_wr"] == 60.0
    assert data[p1_puuid]["duo_label"] == "Synergy Found"

@pytest.mark.asyncio
async def test_live_enrich_learning_phase(mocker):
    mock_riot_get = mocker.patch("app.routes.api.riot_get")
    p1_puuid = "p1-puuid"
    p2_puuid = "p2-puuid"
    m1, m2, m3 = "m1", "m2", "m3"
    
    async def mock_riot_get_impl(client_obj, url):
        if "/league/v4/entries/by-puuid/" in url: return []
        if f"/match/v5/matches/by-puuid/{p1_puuid}/ids" in url: return [m1, m2, m3]
        if f"/match/v5/matches/by-puuid/{p2_puuid}/ids" in url: return [m1, m2, m3]
        
        # 1 win out of 3 games = 33.3% WR -> Learning Phase
        wins = {m1: True, m2: False, m3: False}
        mid = url.split("/")[-1]
        return {
            "metadata": {"matchId": mid},
            "info": {
                "gameDuration": 1200,
                "participants": [
                    {"puuid": p1_puuid, "win": wins.get(mid, False), "championId": 1},
                    {"puuid": p2_puuid, "win": wins.get(mid, False), "championId": 2}
                ]
            }
        }

    mock_riot_get.side_effect = mock_riot_get_impl
    mocker.patch("app.routes.api._compute_perf_score", return_value=75.0)

    payload = {"puuids": [p1_puuid, p2_puuid], "queue_id": 420}
    response = client.post("/live-enrich", json=payload)
    data = response.json()
    
    assert data[p1_puuid]["duo_wr"] == 33.3
    assert data[p1_puuid]["duo_label"] == "Learning Phase"
