import asyncio
import pytest
from unittest.mock import AsyncMock

from app.services import ingestion

@pytest.fixture
def mock_db_status(mocker):
    return mocker.patch("app.services.db._get_ingestion_status_sync")

@pytest.fixture
def mock_sleep(mocker):
    # We raise CancelledError on the first sleep to cleanly exit the infinite loop
    mock = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    mock.side_effect = asyncio.CancelledError()
    return mock

@pytest.mark.asyncio
async def test_worker_paused(mock_db_status, mock_sleep, mocker):
    """Test that when ingestion is paused, it sleeps for 5 seconds."""
    mock_db_status.return_value = {"is_paused": True, "processed_count": 0, "total_target": 100}

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    mock_sleep.assert_called_once_with(5)

@pytest.mark.asyncio
async def test_worker_target_reached(mock_db_status, mock_sleep, mocker):
    """Test that when the target is reached, it sleeps for 60 seconds."""
    mock_db_status.return_value = {"is_paused": False, "processed_count": 100, "total_target": 100}

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    mock_sleep.assert_called_once_with(60)

@pytest.mark.asyncio
async def test_worker_outer_exception(mock_db_status, mock_sleep, mocker):
    """Test that an unexpected outer error triggers a 30 second sleep."""
    mock_db_status.side_effect = Exception("Test exception")

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    mock_sleep.assert_called_once_with(30)

@pytest.mark.asyncio
async def test_worker_empty_ladder(mock_db_status, mocker):
    """Test that when ladder is empty, it advances the tier index."""
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}

    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=AsyncMock)
    mock_riot_get.return_value = [] # Empty entries

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    # 1. sleep for call delay
    # 2. next iteration, sleep because we raise CancelledError to break the loop
    mock_sleep.side_effect = [None, asyncio.CancelledError()]

    # Save the initial tier idx
    initial_tier_idx = ingestion._tier_idx

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    # Check that _tier_idx was incremented and _tier_page reset to 1
    # Note: depends on whether division is None or not, but it advances somehow
    # the code says:
    # if not entries:
    #     _tier_idx += 1
    #     _tier_page = 1
    assert ingestion._tier_idx == initial_tier_idx + 1
    assert ingestion._tier_page == 1

@pytest.mark.asyncio
async def test_worker_happy_path(mock_db_status, mocker):
    """Test the happy path where players are processed."""
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}

    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=AsyncMock)
    # mock a successful ladder fetch
    mock_riot_get.return_value = [
        {"puuid": "player-1"},
        {"puuid": "player-2"}
    ]

    mock_process_player = mocker.patch("app.services.ingestion._process_player", new_callable=AsyncMock)
    mock_process_player.return_value = 1 # saved 1 match

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    # Sleep 1: call delay after fetching ladder
    # Break loop on next cycle
    mock_sleep.side_effect = [None, asyncio.CancelledError()]

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    # Check that process player was called twice, once for each player
    assert mock_process_player.call_count == 2
    mock_process_player.assert_any_call(mocker.ANY, "player-1", {"puuid": "player-1"})
    mock_process_player.assert_any_call(mocker.ANY, "player-2", {"puuid": "player-2"})
