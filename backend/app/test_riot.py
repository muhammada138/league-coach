import pytest
import httpx
import asyncio
from fastapi import HTTPException
from app.services.riot import riot_get, get_match_timeline
from app.state import timeline_cache

@pytest.mark.asyncio
async def test_riot_get_success(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    mock_client.get.return_value = mock_response

    result = await riot_get(mock_client, "http://example.com")
    assert result == {"success": True}
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_riot_get_429_retry(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_response_429 = mocker.Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_response_200 = mocker.Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"success": True}

    mock_client.get.side_effect = [mock_response_429, mock_response_200]

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    result = await riot_get(mock_client, "http://example.com")
    assert result == {"success": True}
    assert mock_client.get.call_count == 2
    mock_sleep.assert_called_once()
    # sleep argument should be retry_after + 0.5 * (attempt + 1)
    # attempt 0 -> retry_after=1 -> sleep(1.5)
    mock_sleep.assert_called_with(1.5)


@pytest.mark.asyncio
async def test_riot_get_max_retries(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_response_429 = mocker.Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_client.get.return_value = mock_response_429

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    with pytest.raises(HTTPException) as exc_info:
        await riot_get(mock_client, "http://example.com")

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Too many requests after multiple retries"
    assert mock_client.get.call_count == 3
    assert mock_sleep.call_count == 3


@pytest.mark.asyncio
async def test_riot_get_http_error(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_response_400 = mocker.Mock()
    mock_response_400.status_code = 400
    mock_response_400.text = "Bad Request"

    mock_client.get.return_value = mock_response_400

    with pytest.raises(HTTPException) as exc_info:
        await riot_get(mock_client, "http://example.com")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Bad Request"
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_get_match_timeline_cache_hit(mocker):
    timeline_cache.cache.clear()
    timeline_cache["match_123"] = {"cached": "data"}

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    result = await get_match_timeline(mock_client, "match_123")
    assert result == {"cached": "data"}
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_match_timeline_cache_miss(mocker):
    timeline_cache.cache.clear()

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_riot_get = mocker.patch("app.services.riot.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.return_value = {"new": "data"}

    result = await get_match_timeline(mock_client, "match_456", "americas")

    assert result == {"new": "data"}
    assert timeline_cache["match_456"] == {"new": "data"}
    mock_riot_get.assert_called_once_with(mock_client, "https://americas.api.riotgames.com/lol/match/v5/matches/match_456/timeline")


@pytest.mark.asyncio
async def test_get_match_timeline_exception(mocker):
    timeline_cache.cache.clear()

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    mock_riot_get = mocker.patch("app.services.riot.riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = Exception("API error")

    result = await get_match_timeline(mock_client, "match_789")

    assert result is None
    assert "match_789" not in timeline_cache

@pytest.mark.asyncio
async def test_get_cached_rank(mocker):
    from app.services.riot import get_cached_rank
    from app.state import rank_cache

    # Clear cache
    rank_cache.cache.clear()

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I"},
        {"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "I"}
    ]
    mock_client.get.return_value = mock_response

    rank = await get_cached_rank(mock_client, "some_puuid", "na1")
    assert rank == "Diamond I"
    mock_client.get.assert_called_once_with(
        "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/some_puuid",
        headers=mocker.ANY
    )
