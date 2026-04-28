import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import time

from app.services import role_identifier

@pytest.fixture(autouse=True)
def reset_cache():
    # Reset globals before each test
    role_identifier._rates = {}
    role_identifier._rates_fetched_at = 0.0
    yield
    # Reset globals after each test
    role_identifier._rates = {}
    role_identifier._rates_fetched_at = 0.0

@pytest.mark.asyncio
async def test_load_rates():
    mock_data = {
        "patch": "14.1",
        "data": {
            "1": {
                "MIDDLE": {"playRate": 0.05},
                "TOP": {"playRate": 0.02}
            },
            "2": {
                "JUNGLE": {"playRate": 0.10}
            }
        }
    }

    mock_response = MagicMock()
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__.return_value = mock_client_instance

    with patch("httpx.AsyncClient", return_value=mock_client_context):
        # 1. First call: Should fetch data
        rates = await role_identifier._load_rates()

        assert 1 in rates
        assert rates[1]["MIDDLE"] == 0.05
        assert rates[1]["TOP"] == 0.02
        assert rates[1]["JUNGLE"] == 0.0 # Default missing to 0.0

        assert 2 in rates
        assert rates[2]["JUNGLE"] == 0.10
        assert rates[2]["MIDDLE"] == 0.0

        assert mock_client_instance.get.call_count == 1

        # 2. Second call: Should use cache
        rates_cached = await role_identifier._load_rates()
        assert rates_cached == rates
        assert mock_client_instance.get.call_count == 1 # Call count shouldn't increase

        # 3. Third call: Expire cache
        role_identifier._rates_fetched_at = time.time() - role_identifier._CACHE_TTL - 10
        rates_expired = await role_identifier._load_rates()
        assert mock_client_instance.get.call_count == 2 # Should refetch

def test_best_assignment_happy_path():
    rates = {
        1: {"TOP": 0.1, "JUNGLE": 0.0},
        2: {"JUNGLE": 0.1, "TOP": 0.0},
        3: {"MIDDLE": 0.1, "BOTTOM": 0.0},
        4: {"BOTTOM": 0.1, "UTILITY": 0.0},
        5: {"UTILITY": 0.1, "MIDDLE": 0.0}
    }
    participants = [
        {"championId": 1, "spells": [4, 12]}, # Flash, Teleport
        {"championId": 2, "spells": [4, 11]}, # Flash, Smite
        {"championId": 3, "spells": [4, 14]}, # Flash, Ignite
        {"championId": 4, "spells": [4, 7]},  # Flash, Heal
        {"championId": 5, "spells": [4, 3]}   # Flash, Exhaust
    ]

    assignment = role_identifier._best_assignment(rates, participants)

    assert assignment[1] == "TOP"
    assert assignment[2] == "JUNGLE"
    assert assignment[3] == "MIDDLE"
    assert assignment[4] == "BOTTOM"
    assert assignment[5] == "UTILITY"


def test_best_assignment_smite_logic():
    # Setup scenario where player 1 has high JUNGLE playrate but NO smite
    # and player 2 has lower JUNGLE playrate but HAS smite.
    # Player 2 should be JUNGLE because of the smite constraint (+1000 penalty/bonus logic).
    rates = {
        1: {"JUNGLE": 0.8, "TOP": 0.1},
        2: {"JUNGLE": 0.2, "TOP": 0.1},
        3: {"MIDDLE": 0.1},
        4: {"BOTTOM": 0.1},
        5: {"UTILITY": 0.1}
    }

    participants = [
        {"championId": 1, "spells": [4, 12]}, # No smite
        {"championId": 2, "spells": [4, 11]}, # Has smite
        {"championId": 3, "spells": [4, 14]},
        {"championId": 4, "spells": [4, 7]},
        {"championId": 5, "spells": [4, 3]}
    ]

    assignment = role_identifier._best_assignment(rates, participants)

    assert assignment[2] == "JUNGLE" # Player 2 gets JUNGLE due to smite
    assert assignment[1] == "TOP"    # Player 1 forced to TOP
    assert assignment[3] == "MIDDLE"
    assert assignment[4] == "BOTTOM"
    assert assignment[5] == "UTILITY"


@pytest.mark.asyncio
async def test_assign_team_roles_success(mocker):
    # Mock dependencies
    mock_load_rates = mocker.patch("app.services.role_identifier._load_rates", return_value={"mock": "rates"})
    mock_best_assignment = mocker.patch("app.services.role_identifier._best_assignment", return_value={1: "JUNGLE"})

    participants = [{"championId": 1, "spells": [4, 11]}]

    result = await role_identifier.assign_team_roles(participants)

    assert result == {1: "JUNGLE"}
    mock_load_rates.assert_called_once()
    mock_best_assignment.assert_called_once_with({"mock": "rates"}, participants)

@pytest.mark.asyncio
async def test_assign_team_roles_fallback(mocker):
    # Mock load_rates to raise an exception
    mocker.patch("app.services.role_identifier._load_rates", side_effect=Exception("API Down"))

    participants = [
        {"championId": 1, "spells": [4, 11]},
        {"championId": 2, "spells": [4, 12]}
    ]

    result = await role_identifier.assign_team_roles(participants)

    # Should fallback to UNKNOWN for all participants
    assert result == {1: "UNKNOWN", 2: "UNKNOWN"}
