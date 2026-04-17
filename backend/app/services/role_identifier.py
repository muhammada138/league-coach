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


def _best_assignment(rates: dict[int, dict[str, float]], participants: list[dict]) -> dict[int, str]:
    """
    participants: list of {"championId": int, "spells": list[int]}
    """
    n = len(participants)
    roles = _ROLES[:n]
    best_score = -1.0
    best: dict[int, str] = {}
    
    # Smite detection
    smite_spell_id = 11
    
    for perm in permutations(roles):
        score = 0.0
        for p, role in zip(participants, perm):
            p_cid = p["championId"]
            p_spells = p.get("spells", [])
            
            # 1. Base Meraki Score (Play Rate)
            score += rates.get(p_cid, {}).get(role, 0.0)
            
            # 2. Smite Signal (The "Constraint")
            has_smite = smite_spell_id in p_spells
            if role == "JUNGLE" and has_smite:
                score += 1000.0  # Massive bonus for Smite in Jungle
            elif role != "JUNGLE" and has_smite:
                score -= 1000.0  # Massive penalty for Smite outside Jungle
            elif role == "JUNGLE" and not has_smite:
                score -= 500.0   # Penalty for Jungle without Smite

        if score > best_score:
            best_score = score
            best = {p["championId"]: role for p, role in zip(participants, perm)}
    return best


async def assign_team_roles(participants: list[dict]) -> dict[int, str]:
    """
    Return {championId: role} for one team.
    participants: list of {"championId": int, "spells": list[int]}
    """
    try:
        rates = await _load_rates()
        return _best_assignment(rates, participants)
    except Exception as exc:
        logger.warning("Role assignment failed: %s", exc)
        return {p["championId"]: "UNKNOWN" for p in participants}
