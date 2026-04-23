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
    # Mock riot_get and get_match_details
    mock_riot_get = mocker.patch("app.routes.live.riot_get")
    mock_get_match = mocker.patch("app.routes.live.get_match_details")
    
    p1_puuid = "p1-puuid"
    p2_puuid = "p2-puuid"
    
    # Shared matches
    m1 = "match-1"
    m2 = "match-2"
    m3 = "match-3"
    
    async def mock_riot_get_impl(client_obj, url):
        if "/league/v4/entries/by-puuid/" in url: return []
        if f"/match/v5/matches/by-puuid/{p1_puuid}/ids" in url: return [m1, m2, m3]
        if f"/match/v5/matches/by-puuid/{p2_puuid}/ids" in url: return [m1, m2, m3]
        return {}

    async def mock_get_match_impl(client_obj, mid, routing):
        return {
            "metadata": {"matchId": mid},
            "info": {
                "gameDuration": 1200,
                "participants": [
                    {"puuid": p1_puuid, "win": True, "championId": 1, "teamPosition": "TOP"},
                    {"puuid": p2_puuid, "win": True, "championId": 2, "teamPosition": "JUNGLE"}
                ]
            }
        }

    mock_riot_get.side_effect = mock_riot_get_impl
    mock_get_match.side_effect = mock_get_match_impl
    
    # Mock compute_perf_score
    mocker.patch("app.routes.live._compute_perf_score", return_value=75.0)

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
    mock_riot_get = mocker.patch("app.routes.live.riot_get")
    mock_get_match = mocker.patch("app.routes.live.get_match_details")
    p1_puuid = "p1-puuid"
    p2_puuid = "p2-puuid"
    m1, m2, m3, m4, m5 = "m1", "m2", "m3", "m4", "m5"
    
    async def mock_riot_get_impl(client_obj, url):
        if "/league/v4/entries/by-puuid/" in url: return []
        if f"/match/v5/matches/by-puuid/{p1_puuid}/ids" in url: return [m1, m2, m3, m4, m5]
        if f"/match/v5/matches/by-puuid/{p2_puuid}/ids" in url: return [m1, m2, m3, m4, m5]
        return {}

    # 3 wins out of 5 games = 60% WR -> Synergy Found
    wins = {m1: True, m2: True, m3: True, m4: False, m5: False}
    
    async def mock_get_match_impl(client_obj, mid, routing):
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
    mock_get_match.side_effect = mock_get_match_impl
    mocker.patch("app.routes.live._compute_perf_score", return_value=75.0)

    payload = {"puuids": [p1_puuid, p2_puuid], "queue_id": 420}
    response = client.post("/live-enrich", json=payload)
    data = response.json()
    
    assert data[p1_puuid]["duo_wr"] == 60.0
    assert data[p1_puuid]["duo_label"] == "Synergy Found"

@pytest.mark.asyncio
async def test_live_enrich_learning_phase(mocker):
    mock_riot_get = mocker.patch("app.routes.live.riot_get")
    mock_get_match = mocker.patch("app.routes.live.get_match_details")
    p1_puuid = "p1-puuid"
    p2_puuid = "p2-puuid"
    m1, m2, m3 = "m1", "m2", "m3"
    
    async def mock_riot_get_impl(client_obj, url):
        if "/league/v4/entries/by-puuid/" in url: return []
        if f"/match/v5/matches/by-puuid/{p1_puuid}/ids" in url: return [m1, m2, m3]
        if f"/match/v5/matches/by-puuid/{p2_puuid}/ids" in url: return [m1, m2, m3]
        return {}

    # 1 win out of 3 games = 33.3% WR -> Learning Phase
    wins = {m1: True, m2: False, m3: False}
    
    async def mock_get_match_impl(client_obj, mid, routing):
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
    mock_get_match.side_effect = mock_get_match_impl
    mocker.patch("app.routes.live._compute_perf_score", return_value=75.0)

    payload = {"puuids": [p1_puuid, p2_puuid], "queue_id": 420}
    response = client.post("/live-enrich", json=payload)
    data = response.json()
    
    assert data[p1_puuid]["duo_wr"] == 33.3
    assert data[p1_puuid]["duo_label"] == "Learning Phase"
