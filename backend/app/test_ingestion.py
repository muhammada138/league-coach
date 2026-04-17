import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services import ingestion
from app.services import db



@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_worker_paused(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": True, "processed_count": 0, "total_target": 100},
        asyncio.CancelledError()
    ]
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    mock_sleep.assert_called_once_with(5)

@pytest.mark.asyncio
async def test_worker_target_reached(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 100, "total_target": 100},
        asyncio.CancelledError()
    ]
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    mock_sleep.assert_called_once_with(60)

@pytest.mark.asyncio
async def test_worker_master_tier(mocker):
    # Set to MASTER tier
    original_idx = ingestion._tier_idx
    # Find MASTER index
    master_idx = next(i for i, t in enumerate(ingestion._SEED_TIERS) if t[0] == "MASTER")
    ingestion._tier_idx = master_idx
    ingestion._tier_page = 1

    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    def mock_status_side_effect():
        yield {"is_paused": False, "processed_count": 0, "total_target": 100} # start
        yield {"is_paused": False, "processed_count": 0, "total_target": 100} # before entries loop
        yield {"is_paused": False, "processed_count": 0, "total_target": 100} # after save 1
        yield asyncio.CancelledError()
    mock_db_status.side_effect = mock_status_side_effect()

    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=AsyncMock)
    mock_riot_get.return_value = {
        "entries": [{"puuid": "player1"}]
    }

    mock_process_player = mocker.patch("app.services.ingestion._process_player", new_callable=AsyncMock)
    mock_process_player.return_value = 1

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    assert ingestion._tier_idx == master_idx + 1
    assert ingestion._tier_page == 1
    mock_process_player.assert_called_once()

    # Restore original idx
    ingestion._tier_idx = original_idx

@pytest.mark.asyncio
async def test_worker_ladder_fetch_failed(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        asyncio.CancelledError()
    ]

    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=AsyncMock)
    mock_riot_get.side_effect = Exception("Ladder fetch failed")

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    original_idx = ingestion._tier_idx

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    assert ingestion._tier_idx == original_idx + 1
    assert ingestion._tier_page == 1

@pytest.mark.asyncio
async def test_worker_normal_tier_advance_page(mocker):
    # Set to BRONZE tier
    original_idx = ingestion._tier_idx
    ingestion._tier_idx = 0
    ingestion._tier_page = 1

    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        asyncio.CancelledError()
    ]

    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=AsyncMock)
    mock_riot_get.return_value = [{"puuid": "player1"}]

    mock_process_player = mocker.patch("app.services.ingestion._process_player", new_callable=AsyncMock)
    mock_process_player.return_value = 0 # No save

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    assert ingestion._tier_idx == 0 # unchanged
    assert ingestion._tier_page == 2 # advanced page

    ingestion._tier_idx = original_idx

@pytest.mark.asyncio
async def test_worker_missing_puuid_and_break(mocker):
    # Tests continue on no puuid, and break if paused in entries loop
    ingestion._tier_idx = 0
    ingestion._tier_page = 1

    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 0, "total_target": 100}, # start
        {"is_paused": False, "processed_count": 0, "total_target": 100}, # before entries loop
        {"is_paused": True, "processed_count": 0, "total_target": 100}, # after player2 saves 1 -> now paused
        asyncio.CancelledError() # Next iteration of while True loop
    ]

    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=AsyncMock)
    mock_riot_get.return_value = [
        {"other_key": "no-puuid"},
        {"puuid": "player2"},
        {"puuid": "player3"}
    ]

    mock_process_player = mocker.patch("app.services.ingestion._process_player", new_callable=AsyncMock)
    mock_process_player.return_value = 1 # Return 1 so it updates status!

    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    # The first entry has no puuid -> continue
    # The second entry saves 1 -> updates status to paused
    # The third entry hits is_paused -> breaks entries loop
    # So _process_player should be called exactly once (for player2)
    mock_process_player.assert_called_once()

@pytest.mark.asyncio
async def test_worker_outer_exception(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        Exception("Test exception"),
        asyncio.CancelledError()
    ]
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    with pytest.raises(asyncio.CancelledError):
        await ingestion.ingestion_worker()

    mock_sleep.assert_called_once_with(30)

from httpx import Response
from app.services.ingestion import _riot_get, _rank_score_from_entry, _player_feats, _compute_seed_form, _process_player
from app.services.win_predictor import MAX_RANK

@pytest.mark.asyncio
async def test_riot_get_success(mocker):
    mock_client = mocker.AsyncMock()
    mock_response = mocker.MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}
    mock_client.get.return_value = mock_response

    result = await _riot_get(mock_client, "http://test")
    assert result == {"data": "test"}
    mock_client.get.assert_called_once()

@pytest.mark.asyncio
async def test_riot_get_429_retry(mocker):
    mock_client = mocker.AsyncMock()
    mock_response_429 = mocker.MagicMock(spec=Response)
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}

    mock_response_200 = mocker.MagicMock(spec=Response)
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"data": "success"}

    mock_client.get.side_effect = [mock_response_429, mock_response_200]
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    result = await _riot_get(mock_client, "http://test")
    assert result == {"data": "success"}
    mock_sleep.assert_called_once_with(3)

@pytest.mark.asyncio
async def test_riot_get_non_200(mocker):
    mock_client = mocker.AsyncMock()
    mock_response = mocker.MagicMock(spec=Response)
    mock_response.status_code = 404
    mock_client.get.return_value = mock_response

    with pytest.raises(RuntimeError, match="Riot 404"):
        await _riot_get(mock_client, "http://test")

def test_rank_score_from_entry_none():
    rank_score, season_wr = _rank_score_from_entry(None)
    assert rank_score == 0.5
    assert season_wr == 0.5

def test_rank_score_from_entry_valid():
    entry = {"tier": "GOLD", "rank": "I", "leaguePoints": 50, "wins": 60, "losses": 40}
    rank_score, season_wr = _rank_score_from_entry(entry)
    expected_rank_score = min((4 + 0.75 + 0.125) / MAX_RANK, 1.0)
    assert rank_score == expected_rank_score
    assert season_wr == 0.6

def test_player_feats():
    entry = {"tier": "GOLD", "rank": "I", "leaguePoints": 50, "wins": 60, "losses": 40}
    feats = _player_feats(entry, form=0.8)
    assert len(feats) == 7
    rank_score, season_wr = _rank_score_from_entry(entry)
    assert feats == [rank_score, season_wr, 0.8, 0.5, 0.5, 0.0, 0.0]

def test_player_feats_none():
    assert _player_feats(None) == [0.5, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0]

def test_compute_seed_form_valid(mocker):
    mock_compute_perf_score = mocker.patch("app.services.ingestion._compute_perf_score")
    mock_compute_perf_score.side_effect = [60.0, 80.0]
    prior_match_data = [
        {"info": {"gameDuration": 1200, "participants": [{"puuid": "seed-puuid"}, {"puuid": "other-puuid"}]}},
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "other-puuid"}, {"puuid": "seed-puuid"}]}}
    ]
    form = _compute_seed_form("seed-puuid", prior_match_data)
    assert form == 0.7

def test_compute_seed_form_no_matches(mocker):
    assert _compute_seed_form("seed-puuid", []) == 0.5

def test_compute_seed_form_player_not_found(mocker):
    prior_match_data = [{"info": {"gameDuration": 1200, "participants": [{"puuid": "other-puuid"}]}}]
    assert _compute_seed_form("seed-puuid", prior_match_data) == 0.5

def test_compute_seed_form_exception(mocker):
    prior_match_data = [{"wrong_key": "data"}]
    assert _compute_seed_form("seed-puuid", prior_match_data) == 0.5

@pytest.mark.asyncio
async def test_process_player_paused(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": True, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    assert await _process_player(mock_client, "puuid", None) == 0

@pytest.mark.asyncio
async def test_process_player_match_id_fetch_fails(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = Exception("Fetch failed")
    mock_client = mocker.AsyncMock()
    assert await _process_player(mock_client, "puuid", None) == 0

@pytest.mark.asyncio
async def test_process_player_success(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["mid1"],
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "seed-puuid", "teamId": 100, "win": True}, {"puuid": "other-puuid", "teamId": 200, "win": False}]}},
        [{"queueType": "RANKED_SOLO_5x5", "tier": "SILVER"}]
    ]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_db_save = mocker.patch("app.services.db.save_training_match", new_callable=mocker.AsyncMock)
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)

    assert await _process_player(mock_client, "seed-puuid", {"tier": "GOLD"}) == 1
    mock_db_save.assert_called_once()
    args, kwargs = mock_db_save.call_args
    assert args[0] == "mid1"

@pytest.mark.asyncio
async def test_process_player_no_new_matches(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.return_value = ["mid1"]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = True
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "puuid", None) == 0

@pytest.mark.asyncio
async def test_process_player_match_details_exception(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [["mid1"], Exception("Match fetch failed")]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "puuid", None) == 0

@pytest.mark.asyncio
async def test_process_player_other_puuids_exception_and_empty_teams(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["mid1"],
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "seed-puuid", "teamId": 100, "win": True}, {"puuid": "other-puuid-unique-123", "teamId": 100, "win": True}]}},
        Exception("Rank fetch failed")
    ]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "seed-puuid", None) == 0

@pytest.mark.asyncio
async def test_process_player_feature_extraction_exception(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["mid1"],
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "seed-puuid", "teamId": 100, "win": True}, {"puuid": "other-puuid-unique-123", "teamId": 200, "win": False}]}},
        [{"queueType": "RANKED_SOLO_5x5", "tier": "SILVER"}]
    ]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_db_save = mocker.patch("app.services.db.save_training_match", new_callable=mocker.AsyncMock)
    mock_db_save.side_effect = Exception("Save failed")
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "seed-puuid", {"tier": "GOLD"}) == 0

@pytest.mark.asyncio
async def test_process_player_break_mid_loop(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": True, "processed_count": 0, "total_target": 100}
    ]
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.return_value = ["mid1"]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "puuid", None) == 0

@pytest.mark.asyncio
async def test_process_player_break_ordered_loop(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": True, "processed_count": 0, "total_target": 100}
    ]
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["mid1"],
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "seed-puuid", "teamId": 100, "win": True}, {"puuid": "other-puuid-unique-123", "teamId": 200, "win": False}]}},
        [{"queueType": "RANKED_SOLO_5x5", "tier": "SILVER"}]
    ]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "seed-puuid", {"tier": "GOLD"}) == 0

@pytest.mark.asyncio
async def test_process_player_paused_in_other_puuids(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.side_effect = [
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": False, "processed_count": 0, "total_target": 100},
        {"is_paused": True, "processed_count": 0, "total_target": 100}
    ]
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["mid1"],
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "seed-puuid", "teamId": 100, "win": True}, {"puuid": "other-puuid-unique-123", "teamId": 200, "win": False}]}}
    ]
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "seed-puuid", {"tier": "GOLD"}) == 0

@pytest.mark.asyncio
async def test_process_player_rank_cache_hit(mocker):
    mock_db_status = mocker.patch("app.services.db._get_ingestion_status_sync")
    mock_db_status.return_value = {"is_paused": False, "processed_count": 0, "total_target": 100}
    mock_client = mocker.AsyncMock()
    mock_riot_get = mocker.patch("app.services.ingestion._riot_get", new_callable=mocker.AsyncMock)
    mock_riot_get.side_effect = [
        ["mid1"],
        {"info": {"gameDuration": 1500, "participants": [{"puuid": "seed-puuid", "teamId": 100, "win": True}, {"puuid": "other-puuid-cached", "teamId": 200, "win": False}]}}
    ]
    from app.services.ingestion import _rank_cache_set
    _rank_cache_set("other-puuid-cached", {"queueType": "RANKED_SOLO_5x5", "tier": "GOLD"})
    mock_db_has_training = mocker.patch("app.services.db.has_training_match", new_callable=mocker.AsyncMock)
    mock_db_has_training.return_value = False
    mock_db_save = mocker.patch("app.services.db.save_training_match", new_callable=mocker.AsyncMock)
    mock_sleep = mocker.patch("asyncio.sleep", new_callable=mocker.AsyncMock)
    assert await _process_player(mock_client, "seed-puuid", {"tier": "GOLD"}) == 1
