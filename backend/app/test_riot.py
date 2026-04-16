import pytest
import httpx
import asyncio
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.riot import riot_get

@pytest.fixture
def mock_sleep(mocker):
    return mocker.patch("asyncio.sleep", new_callable=AsyncMock)

@pytest.mark.asyncio
async def test_riot_get_success(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}
    mock_client.get.return_value = mock_response

    result = await riot_get(mock_client, "http://test.url")
    assert result == {"data": "test"}
    mock_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_riot_get_429_then_success(mocker, mock_sleep):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)

    mock_response_429 = mocker.Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "2"}

    mock_response_200 = mocker.Mock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"data": "success"}

    mock_client.get.side_effect = [mock_response_429, mock_response_200]

    result = await riot_get(mock_client, "http://test.url")

    assert result == {"data": "success"}
    assert mock_client.get.call_count == 2
    mock_sleep.assert_called_once_with(2 + 0.5 * 1) # retry_after + 0.5 * attempt

@pytest.mark.asyncio
async def test_riot_get_429_exhausted(mocker, mock_sleep):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)

    mock_response_429 = mocker.Mock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_client.get.side_effect = [mock_response_429, mock_response_429, mock_response_429]

    with pytest.raises(HTTPException) as excinfo:
        await riot_get(mock_client, "http://test.url")

    assert excinfo.value.status_code == 429
    assert excinfo.value.detail == "Too many requests after multiple retries"
    assert mock_client.get.call_count == 3
    assert mock_sleep.call_count == 3

@pytest.mark.asyncio
async def test_riot_get_non_200(mocker):
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)

    mock_response_error = mocker.Mock()
    mock_response_error.status_code = 500
    mock_response_error.text = "Internal Server Error"

    mock_client.get.return_value = mock_response_error

    with pytest.raises(HTTPException) as excinfo:
        await riot_get(mock_client, "http://test.url")

    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Internal Server Error"
    assert mock_client.get.call_count == 1

@pytest.mark.asyncio
async def test_get_cached_rank_empty_puuid(mocker):
    from app.services.riot import get_cached_rank
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)
    assert await get_cached_rank(mock_client, "") == "Unranked"

@pytest.mark.asyncio
async def test_get_cached_rank_cache_hit(mocker):
    from app.services.riot import get_cached_rank
    from app.state import rank_cache

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)
    rank_cache["test-puuid"] = "Gold IV"

    assert await get_cached_rank(mock_client, "test-puuid") == "Gold IV"
    mock_client.get.assert_not_called()

    # cleanup cache
    del rank_cache.cache["test-puuid"]

@pytest.mark.asyncio
async def test_get_cached_rank_cache_miss(mocker):
    from app.services.riot import get_cached_rank
    from app.state import rank_cache

    # Ensure cache is clean
    if "test-puuid-miss" in rank_cache:
        del rank_cache.cache["test-puuid-miss"]

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I"},
        {"queueType": "RANKED_SOLO_5x5", "tier": "PLATINUM", "rank": "III"}
    ]
    mock_client.get.return_value = mock_response

    rank = await get_cached_rank(mock_client, "test-puuid-miss")
    assert rank == "Platinum III"
    assert rank_cache["test-puuid-miss"] == "Platinum III"

@pytest.mark.asyncio
async def test_get_cached_rank_no_solo_queue(mocker):
    from app.services.riot import get_cached_rank
    from app.state import rank_cache

    if "test-puuid-flex" in rank_cache:
        del rank_cache.cache["test-puuid-flex"]

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I"}
    ]
    mock_client.get.return_value = mock_response

    rank = await get_cached_rank(mock_client, "test-puuid-flex")
    assert rank == "Unranked"
    assert rank_cache["test-puuid-flex"] == "Unranked"

@pytest.mark.asyncio
async def test_get_cached_rank_exception(mocker):
    from app.services.riot import get_cached_rank

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("app.services.db.get_lp_history", new_callable=mocker.AsyncMock)
    mock_client.get.side_effect = Exception("API Error")

    rank = await get_cached_rank(mock_client, "test-puuid-err")
    assert rank == "Unranked"
