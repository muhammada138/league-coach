import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, mock_open, MagicMock
from pathlib import Path

from app.services.meta_scraper import (
    get_meta_data,
    save_meta_data,
    is_sync_active,
    is_sync_paused,
    get_sync_mode,
    toggle_pause,
    cancel_sync,
    _get_latest_version_full,
    get_patch_at_offset,
    fetch_champion_matchups,
    fetch_rank_meta,
    sync_meta,
    sync_state
)

@pytest.fixture(autouse=True)
def reset_sync_state():
    """Reset the global sync state before each test."""
    sync_state["active"] = False
    sync_state["paused"] = False
    sync_state["cancel_requested"] = False
    sync_state["mode"] = "idle"
    yield

def test_sync_state_functions():
    assert is_sync_active() is False
    assert is_sync_paused() is False
    assert get_sync_mode() == "idle"

    assert toggle_pause() is True
    assert is_sync_paused() is True
    assert toggle_pause() is False

    assert cancel_sync() is False
    sync_state["active"] = True
    assert cancel_sync() is True
    assert sync_state["cancel_requested"] is True

def test_get_meta_data_exists(mocker):
    test_data = {"test": "data"}
    # Patch the Path instance itself, not the class attribute
    mock_path = mocker.Mock(spec=Path)
    mock_path.exists.return_value = True
    mocker.patch("app.services.meta_scraper.META_FILE_PATH", mock_path)
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(test_data)))
    assert get_meta_data() == test_data

def test_get_meta_data_missing(mocker):
    mock_path = mocker.Mock(spec=Path)
    mock_path.exists.return_value = False
    mocker.patch("app.services.meta_scraper.META_FILE_PATH", mock_path)
    assert get_meta_data() == {}

def test_get_meta_data_corrupt(mocker):
    mock_path = mocker.Mock(spec=Path)
    mock_path.exists.return_value = True
    mocker.patch("app.services.meta_scraper.META_FILE_PATH", mock_path)
    mocker.patch("builtins.open", mock_open(read_data="invalid json"))
    assert get_meta_data() == {}

def test_save_meta_data(mocker):
    test_data = {"test": "data"}
    mock_file = mock_open()
    mocker.patch("builtins.open", mock_file)
    mocker.patch("os.replace")

    save_meta_data(test_data)
    mock_file.assert_called_once()

@pytest.mark.asyncio
async def test_get_patch_at_offset(mocker):
    # Test successful fetch
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ["14.8.1", "14.7.1", "14.6.1"]

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    # Need to patch the async context manager correctly
    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    assert await get_patch_at_offset(0) == "14.8"
    assert await get_patch_at_offset(1) == "14.7"

    # Test fallback on empty array
    mock_resp.json.return_value = []
    assert await get_patch_at_offset(0) == "14.8"

    # Test fallback on exception
    mock_client.get.side_effect = Exception("Network error")
    assert await get_patch_at_offset(0) == "14.8"

@pytest.mark.asyncio
async def test_get_latest_version_full(mocker):
    # Reset globals
    import app.services.meta_scraper as ms
    ms._CACHED_FULL_VERSION = None
    ms._VERSION_CACHE_TIME = 0

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ["14.8.1", "14.7.1"]

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    # First call should hit the API
    assert await _get_latest_version_full() == "14.8.1"
    assert mock_client.get.call_count == 1

    # Second call should use cache
    assert await _get_latest_version_full() == "14.8.1"
    assert mock_client.get.call_count == 1

@pytest.mark.asyncio
async def test_fetch_rank_meta(mocker):
    # Mocking ensure_champ_ids
    mocker.patch("app.services.meta_scraper._ensure_champ_ids", return_value=None)
    import app.services.meta_scraper as ms
    ms._CHAMP_ID_MAP = {"Aatrox": 266}
    ms._ID_CHAMP_MAP = {"266": {"id": 266, "name": "Aatrox", "slug": "aatrox"}}

    # Mock httpx response for Qwik JSON
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"some": "invalid json at first"}'

    # Needs a better mock to actually simulate Qwik state parsing
    # Let's mock the Qwik JSON content specifically
    mock_qwik_json = {
        "objs": [
            "placeholder",
            {"wr": 1, "games": 2, "tier": 3, "rank": 4},
            "50.5", "1000", "1", "2"
        ],
        "ctxs": {
            "some_id": {
                "r": "1"
            }
        }
    }

    html_content = f'''
    <html>
        <body>
            <script type="qwik/json">{json.dumps(mock_qwik_json)}</script>
        </body>
    </html>
    '''
    mock_resp.text = html_content

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    # Call the function
    result = await fetch_rank_meta("gold", patch="14.8")

    # It should return a default structure if parsing fails or succeeds with no champs
    assert "tier_avg" in result
    assert "champions" in result

    # Test fallback on exception
    mock_client.get.side_effect = Exception("Network error")
    result_error = await fetch_rank_meta("gold", patch="14.8")
    assert result_error == {"tier_avg": 50.0, "champions": {}}

@pytest.mark.asyncio
async def test_fetch_champion_matchups(mocker):
    # Mocking ensure_champ_ids
    mocker.patch("app.services.meta_scraper._ensure_champ_ids", return_value=None)
    import app.services.meta_scraper as ms
    ms._CHAMP_ID_MAP = {"Aatrox": 266, "Ahri": 103}
    ms._ID_CHAMP_MAP = {"266": {"id": 266, "name": "Aatrox", "slug": "aatrox"}, "103": {"id": 103, "name": "Ahri", "slug": "ahri"}}

    # Mock httpx response for matchups
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_qwik_json = {
        "objs": [
            "placeholder",
            {"enemy": 1, "wr": 2, "games": 3},
            "103", "45.5", "100"
        ],
        "ctxs": {
            "some_id": {
                "r": "1"
            }
        }
    }

    html_content = f'''
    <html>
        <body>
            <script type="qwik/json">{json.dumps(mock_qwik_json)}</script>
        </body>
    </html>
    '''
    mock_resp.text = html_content

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client_cls.return_value.__aenter__.return_value = mock_client

    result = await fetch_champion_matchups("gold", "aatrox", "top", patch="14.8")

    assert isinstance(result, dict)

    # Test fallback on exception
    mock_client.get.side_effect = Exception("Network error")
    result_error = await fetch_champion_matchups("gold", "aatrox", "top", patch="14.8")
    assert result_error == {}

@pytest.mark.asyncio
async def test_sync_meta(mocker):
    # Mock all the heavy lifting functions
    mocker.patch("app.services.meta_scraper.get_patch_at_offset", side_effect=["14.8", "14.7"])

    mock_get_meta = mocker.patch("app.services.meta_scraper.get_meta_data", return_value={"data": {}})
    mock_save = mocker.patch("app.services.meta_scraper.save_meta_data")

    # Mocking sleep to avoid actual waiting
    mocker.patch("asyncio.sleep", return_value=None)

    # Return some fake data for tierlist
    mock_fetch_rank = mocker.patch("app.services.meta_scraper.fetch_rank_meta")
    mock_fetch_rank.return_value = {
        "tier_avg": 50.0,
        "champions": {
            "266:top": {"cid": "266", "name": "aatrox", "lane": "top", "wr": 51.0, "games": 1000}
        }
    }

    # Run a sync (using only "iron" rank to speed up or mock RANKS if possible,
    # but since RANKS is a global, we'll let it run through or limit it if slow)
    # Actually, we can patch RANKS to just one rank for testing
    mocker.patch("app.services.meta_scraper.RANKS", ["gold"])

    result = await sync_meta(mode="tierlist")

    assert result is True
    # Verify save was called at least once
    assert mock_save.call_count >= 1

@pytest.mark.asyncio
async def test_sync_meta_already_active(mocker):
    # Set sync to active and try to sync
    sync_state["active"] = True

    result = await sync_meta(mode="tierlist")

    assert result is False

@pytest.mark.asyncio
async def test_sync_meta_cancel(mocker):
    # Mock to sleep which we'll interrupt
    mocker.patch("app.services.meta_scraper.get_patch_at_offset", side_effect=["14.8", "14.7"])
    mocker.patch("app.services.meta_scraper.get_meta_data", return_value={"data": {}})
    mock_save = mocker.patch("app.services.meta_scraper.save_meta_data")

    async def mock_fetch_rank_meta(*args, **kwargs):
        # Request cancel during fetch
        sync_state["cancel_requested"] = True
        return {"tier_avg": 50.0, "champions": {}}

    mocker.patch("app.services.meta_scraper.fetch_rank_meta", side_effect=mock_fetch_rank_meta)
    mocker.patch("app.services.meta_scraper.RANKS", ["gold", "silver"])

    result = await sync_meta(mode="tierlist")

    assert result is True
    # The loop should break early
