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
    assert response.json()["coaching"] == "1. Play better.\n2. Farm more."
    
