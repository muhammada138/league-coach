"""
Role identification for live games using Meraki Analytics champion play-rate data.

Algorithm (same as meraki-analytics/role-identification):
  For each team of 5 champions, enumerate all 5! = 120 role permutations and pick
  the assignment that maximises the sum of per-champion play-rates for assigned roles.
  Data source: cdn.merakianalytics.com/riot/lol/resources/latest/en-US/championrates.json
  Cached for 24 hours — patch updates are infrequent and stale data is fine.
"""

import time
import logging
import httpx
from itertools import permutations

logger = logging.getLogger(__name__)

_MERAKI_URL = "http://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/championrates.json"
_ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
_CACHE_TTL = 86400  # 24 hours

_rates: dict[int, dict[str, float]] = {}
_rates_fetched_at: float = 0.0


async def _load_rates() -> dict[int, dict[str, float]]:
    global _rates, _rates_fetched_at
    if _rates and (time.time() - _rates_fetched_at) < _CACHE_TTL:
        return _rates
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(_MERAKI_URL)
        resp.raise_for_status()
        data = resp.json()
    result: dict[int, dict[str, float]] = {}
    for champ_id_str, positions in data.get("data", {}).items():
        result[int(champ_id_str)] = {
            role: positions.get(role, {}).get("playRate", 0.0)
            for role in _ROLES
        }
    _rates = result
    _rates_fetched_at = time.time()
    logger.info("Meraki champion rates loaded (patch %s, %d champions)", data.get("patch"), len(result))
    return _rates


def _best_assignment(rates: dict[int, dict[str, float]], champ_ids: list[int]) -> dict[int, str]:
    n = len(champ_ids)
    roles = _ROLES[:n]
    best_score = -1.0
    best: dict[int, str] = {}
    for perm in permutations(roles):
        score = sum(rates.get(cid, {}).get(role, 0.0) for cid, role in zip(champ_ids, perm))
        if score > best_score:
            best_score = score
            best = {cid: role for cid, role in zip(champ_ids, perm)}
    return best


async def assign_team_roles(champ_ids: list[int]) -> dict[int, str]:
    """Return {championId: role} for one team. Returns UNKNOWN for all on error."""
    try:
        rates = await _load_rates()
        return _best_assignment(rates, champ_ids)
    except Exception as exc:
        logger.warning("Role assignment failed: %s", exc)
        return {cid: "UNKNOWN" for cid in champ_ids}
