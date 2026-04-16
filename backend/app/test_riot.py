import pytest
import httpx
import asyncio
from fastapi import HTTPException
from app.services.riot import (
    riot_get,
    get_cached_rank,
    get_match_timeline,
    _compute_perf_score,
    _compute_diffed_lane
)
from app.state import rank_cache, timeline_cache

@pytest.mark.asyncio
async def test_riot_get_success(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "value"}
    mock_client.get.return_value = mock_response

    result = await riot_get(mock_client, "http://test")
    assert result == {"key": "value"}
    mock_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_riot_get_429_retry(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    mock_response_429 = mocker.Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_response_200 = mocker.Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"success": True}

    mock_client.get.side_effect = [mock_response_429, mock_response_200]

    result = await riot_get(mock_client, "http://test")
    assert result == {"success": True}
    assert mock_client.get.call_count == 2
    mock_sleep.assert_called_once()

@pytest.mark.asyncio
async def test_riot_get_429_exhausted(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    mock_response_429 = mocker.Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_client.get.return_value = mock_response_429

    with pytest.raises(HTTPException) as exc:
        await riot_get(mock_client, "http://test")

    assert exc.value.status_code == 429
    assert mock_client.get.call_count == 3
    assert mock_sleep.call_count == 3

@pytest.mark.asyncio
async def test_riot_get_error(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_response_err = mocker.Mock()
    mock_response_err.status_code = 400
    mock_response_err.text = "Bad Request"

    mock_client.get.return_value = mock_response_err

    with pytest.raises(HTTPException) as exc:
        await riot_get(mock_client, "http://test")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Bad Request"

@pytest.mark.asyncio
async def test_get_cached_rank(mocker):
    # Clear the cache before tests
    rank_cache.cache.clear()

    # 1. Test missing puuid
    rank = await get_cached_rank(None, "")
    assert rank == "Unranked"

    # 2. Test cache miss (calls API)
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
    assert "puuid-789" not in rank_cache

@pytest.mark.asyncio
async def test_get_match_timeline_cache_hit(mocker):
    timeline_cache["match_123"] = {"cached": "data"}
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    result = await get_match_timeline(mock_client, "match_123")
    assert result == {"cached": "data"}
    mock_client.get.assert_not_called()

@pytest.mark.asyncio
async def test_get_match_timeline_cache_miss(mocker):
    timeline_cache.cache.clear()
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"timeline": "data"}
    mock_client.get.return_value = mock_response

    result = await get_match_timeline(mock_client, "match_456")
    assert result == {"timeline": "data"}
    assert "match_456" in timeline_cache
    assert timeline_cache["match_456"] == {"timeline": "data"}

@pytest.mark.asyncio
async def test_get_match_timeline_exception(mocker):
    timeline_cache.cache.clear()
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = Exception("Timeline Error")

    result = await get_match_timeline(mock_client, "match_789")
    assert result is None
    assert "match_789" not in timeline_cache

def test_compute_perf_score():
    player_top = {
        "teamPosition": "TOP",
        "win": True,
        "kills": 5, "deaths": 2, "assists": 5,
        "challenges": {
            "laneMinionsFirst10Minutes": 60,
            "turretPlatesTaken": 2,
            "soloKills": 1,
            "turretTakedowns": 1
        }
    }
    score_top = _compute_perf_score(player_top, [player_top], game_duration=1200)
    assert score_top > 0

    player_jg = {
        "teamPosition": "JUNGLE",
        "win": False,
        "kills": 3, "deaths": 3, "assists": 5,
        "challenges": {
            "initialCrabCount": 1,
            "scuttleCrabKills": 2,
            "jungleCsBefore10Minutes": 50,
            "enemyJungleMonsterKills": 10,
            "pickKillWithAlly": 2
        }
    }
    score_jg = _compute_perf_score(player_jg, [player_jg], game_duration=1200)
    assert score_jg > 0

    player_sup = {
        "teamPosition": "UTILITY",
        "win": True,
        "kills": 1, "deaths": 2, "assists": 15,
        "challenges": {
            "completeSupportQuestInTime": 1,
            "stealthWardsPlaced": 20,
            "controlWardsPlaced": 5,
            "wardTakedowns": 3,
            "pickKillWithAlly": 5
        }
    }
    score_sup = _compute_perf_score(player_sup, [player_sup], game_duration=1200)
    assert score_sup > 0

    # Early surrender
    score_early = _compute_perf_score(player_sup, [player_sup], game_duration=150)
    assert score_early == 0.0

def test_compute_diffed_lane():
    p1 = {
        "teamPosition": "MIDDLE",
        "teamId": 100,
        "participantId": 1,
        "win": True,
        "kills": 10, "deaths": 0, "assists": 5,
        "goldEarned": 10000,
        "champExperience": 12000
    }
    p2 = {
        "teamPosition": "MIDDLE",
        "teamId": 200,
        "participantId": 2,
        "win": False,
        "kills": 0, "deaths": 10, "assists": 0,
        "goldEarned": 5000,
        "champExperience": 6000
    }
    all_players = [p1, p2]

    diffed = _compute_diffed_lane(all_players, game_duration=1200)
    assert diffed == "MIDDLE"
