"""
ML Data Ingestion Worker — accumulates real match data for win predictor retraining.

Strategy
--------
Cycles through BRONZE→SILVER→GOLD→PLATINUM→EMERALD→DIAMOND→MASTER ladder pages.
For each seed player it fetches their last 10 ranked match IDs, then for each
new match:
  - Fetches rank (tier/WR) for ALL 10 participants — cached globally with 1hr TTL
    so repeat participants across seed players cost zero extra calls
  - Computes seed player's form_score from their PREVIOUS matches in the batch
    (e.g. training on match[0] uses perf from match[1]-match[5]) — no leakage
  - Other 9 players get neutral form (0.5) — real rank/WR is the key signal

Feature vector per player (7-dim):
  [rank_score, season_wr, form_score, 0.5, 0.5, 0.0, 0.0]

Rate limiting
-------------
Semaphore(1) + 1.25s sleep between every Riot API call.
Throughput: ~9 matches/min cold start → ~43 matches/min once rank cache warms up.
Cache holds ~50k PUUIDs (≈15 MB) with 1hr TTL — most participants seen in the same
rank tier repeat frequently, so hit rate climbs quickly after the first few pages.
"""

import asyncio
import logging
import time as _time

import httpx
import numpy as np

from ..state import RIOT_REGION, RIOT_ROUTING, RIOT_HEADERS
from ..services.riot import _compute_perf_score
from ..services.win_predictor import TIER_SCORE, DIV_BONUS, MAX_RANK
from ..services import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_sem = asyncio.Semaphore(1)
_CALL_DELAY = 1.25

_SEED_TIERS = [
    # Bronze — lower-elo representation
    ("BRONZE",   "I"),
    ("BRONZE",   "II"),
    # Silver
    ("SILVER",   "I"),
    ("SILVER",   "II"),
    ("SILVER",   "III"),
    ("SILVER",   "IV"),
    # Gold
    ("GOLD",     "I"),
    ("GOLD",     "II"),
    ("GOLD",     "III"),
    ("GOLD",     "IV"),
    # Platinum
    ("PLATINUM", "I"),
    ("PLATINUM", "II"),
    ("PLATINUM", "III"),
    ("PLATINUM", "IV"),
    # Emerald (added Season 2023, between Platinum and Diamond)
    ("EMERALD",  "I"),
    ("EMERALD",  "II"),
    ("EMERALD",  "III"),
    ("EMERALD",  "IV"),
    # Diamond
    ("DIAMOND",  "I"),
    ("DIAMOND",  "II"),
    ("DIAMOND",  "III"),
    ("DIAMOND",  "IV"),
    # Master — single-page endpoint, no division
    ("MASTER",   None),
]

_tier_idx  = 0
_tier_page = 1

# ---------------------------------------------------------------------------
# Persistent rank cache — shared across all seed players, survives page loops
# ---------------------------------------------------------------------------
# puuid -> (rank_entry | None, fetched_at_timestamp)
_rank_cache: dict[str, tuple] = {}
_RANK_TTL = 3600  # 1 hour — rank changes rarely during a session


def _rank_cache_get(puuid: str) -> tuple[bool, dict | None]:
    item = _rank_cache.get(puuid)
    if item and (_time.time() - item[1]) < _RANK_TTL:
        return True, item[0]
    return False, None


def _rank_cache_set(puuid: str, entry: dict | None) -> None:
    _rank_cache[puuid] = (entry, _time.time())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _riot_get(client: httpx.AsyncClient, url: str):
    """Minimal Riot GET with 429 back-off. Raises on non-200."""
    for attempt in range(3):
        response = await client.get(url, headers=RIOT_HEADERS)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            logger.warning("Ingest 429 – sleeping %ds (attempt %d)", retry_after + 2, attempt + 1)
            await asyncio.sleep(retry_after + 2)
            continue
        if response.status_code != 200:
            raise RuntimeError(f"Riot {response.status_code} @ {url}")
        return response.json()
    raise RuntimeError("Max retries exceeded")


def _rank_score_from_entry(entry: dict | None) -> tuple[float, float]:
    """Return (rank_score, season_wr) from a LeagueEntry dict, or (0.5, 0.5)."""
    if not entry:
        return 0.5, 0.5
    tier_val   = TIER_SCORE.get(entry.get("tier", "SILVER"), 3.5)
    div_val    = DIV_BONUS.get(entry.get("rank", ""), 0.0)
    lp_bonus   = (entry.get("leaguePoints", 0) / 100.0) * 0.25
    rank_score = min((tier_val + div_val + lp_bonus) / MAX_RANK, 1.0)

    w = entry.get("wins", 0)
    l = entry.get("losses", 0)
    raw_wr    = w / (w + l) if (w + l) > 0 else 0.5
    conf      = min((w + l) / 100.0, 1.0)
    season_wr = raw_wr * conf + 0.5 * (1.0 - conf)
    return rank_score, season_wr


def _player_feats(rank_entry: dict | None, form: float = 0.5) -> list[float]:
    """7-dim feature vector. form should come from previous matches (no leakage)."""
    rank_score, season_wr = _rank_score_from_entry(rank_entry)
    return [rank_score, season_wr, form, 0.5, 0.5, 0.0, 0.0]


def _compute_seed_form(puuid: str, prior_match_data: list[dict]) -> float:
    """
    Avg performance score of the seed player across prior_match_data.
    Uses match data from OLDER matches in the batch — no outcome leakage.
    """
    scores = []
    for match_data in prior_match_data:
        try:
            info         = match_data["info"]
            participants = info["participants"]
            duration     = info["gameDuration"]
            p = next((x for x in participants if x.get("puuid") == puuid), None)
            if p:
                score = float(_compute_perf_score(p, participants, None, duration)) / 100.0
                scores.append(score)
        except Exception:
            continue
    return sum(scores) / len(scores) if scores else 0.5


async def _process_player(
    client: httpx.AsyncClient,
    puuid: str,
    seed_rank_entry: dict | None,
) -> int:
    """
    Fetch and persist training samples from one player's recent matches.

    Improvements over v1:
    - Rank fetched for ALL 10 participants per match (real rank/WR signal for everyone)
    - Seed player's form computed from previous matches in batch (no leakage)
    Returns the number of new matches saved.
    """
    status = db._get_ingestion_status_sync()
    if status["is_paused"] or status["processed_count"] >= status["total_target"]:
        return 0

    # Step 1: Fetch match IDs
    async with _sem:
        try:
            match_ids = await _riot_get(
                client,
                f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
                f"?count=10&queue=420",
            )
        except Exception as exc:
            logger.debug("Match IDs failed for %.12s: %s", puuid, exc)
            return 0
    await asyncio.sleep(_CALL_DELAY)

    # Step 2: Fetch match details for all new matches
    match_details: dict[str, dict] = {}
    for mid in match_ids:
        status = db._get_ingestion_status_sync()
        if status["is_paused"] or status["processed_count"] >= status["total_target"]:
            break
        if await db.has_training_match(mid):
            continue
        async with _sem:
            try:
                match_details[mid] = await _riot_get(
                    client,
                    f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}",
                )
            except Exception as exc:
                logger.debug("Match fetch failed %s: %s", mid, exc)
        await asyncio.sleep(_CALL_DELAY)

    if not match_details:
        return 0

    # Step 3: Collect all unique non-seed PUUIDs across all fetched matches
    other_puuids: set[str] = set()
    for data in match_details.values():
        for p in data["info"]["participants"]:
            uid = p.get("puuid")
            if uid and uid != puuid:
                other_puuids.add(uid)

    # Step 4: Resolve rank for every unique non-seed participant.
    # Check the global TTL cache first — participants repeat across seed players
    # within the same rank tier, so cache hit rate climbs quickly after warmup.
    _rank_cache_set(puuid, seed_rank_entry)  # seed is already fresh
    rank_cache: dict[str, dict | None] = {puuid: seed_rank_entry}

    for other_puuid in other_puuids:
        hit, cached_entry = _rank_cache_get(other_puuid)
        if hit:
            rank_cache[other_puuid] = cached_entry
            continue

        status = db._get_ingestion_status_sync()
        if status["is_paused"]:
            return 0

        async with _sem:
            try:
                entries = await _riot_get(
                    client,
                    f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{other_puuid}",
                )
            except Exception:
                entries = []
        await asyncio.sleep(_CALL_DELAY)

        entry = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
        _rank_cache_set(other_puuid, entry)
        rank_cache[other_puuid] = entry

    # Step 5: Build ordered list of new match IDs (newest → oldest, API order)
    ordered = [mid for mid in match_ids if mid in match_details]

    # Step 6: Save training samples — seed player's form from older matches in batch
    saved = 0
    status = db._get_ingestion_status_sync()
    for i, mid in enumerate(ordered):
        if status["is_paused"] or status["processed_count"] + saved >= status["total_target"]:
            break

        try:
            info         = match_details[mid]["info"]
            participants = info["participants"]
            duration     = info["gameDuration"]

            blue = [p for p in participants if p["teamId"] == 100]
            red  = [p for p in participants if p["teamId"] == 200]
            if len(blue) < 1 or len(red) < 1:
                continue

            # Seed player form = avg perf in matches[i+1 … i+5] (older = higher index)
            prior = [match_details[ordered[j]] for j in range(i + 1, min(i + 6, len(ordered)))]
            seed_form = _compute_seed_form(puuid, prior)

            def team_vec(players: list) -> list[float]:
                feats = [
                    _player_feats(
                        rank_cache.get(p.get("puuid")),
                        seed_form if p.get("puuid") == puuid else 0.5,
                    )
                    for p in players
                ]
                return np.mean(feats, axis=0).tolist()

            blue_feats = team_vec(blue)
            red_feats  = team_vec(red)
            blue_won   = any(p.get("win") for p in blue)

            await db.save_training_match(mid, blue_feats, red_feats, blue_won)
            saved += 1

        except Exception as exc:
            logger.debug("Feature extraction failed for %s: %s", mid, exc)

    return saved


# ---------------------------------------------------------------------------
# Public worker — started once in main.py lifespan
# ---------------------------------------------------------------------------

async def ingestion_worker() -> None:
    """
    Long-running background task. Paused by default — resume via POST /ingest/toggle.
    Safely handles cancellation on shutdown.
    """
    global _tier_idx, _tier_page
    logger.info("ML ingestion worker started (paused by default)")

    while True:
        try:
            status = db._get_ingestion_status_sync()

            if status["is_paused"]:
                await asyncio.sleep(5)
                continue

            if status["processed_count"] >= status["total_target"]:
                logger.info(
                    "Ingestion target reached (%d / %d). Worker idle.",
                    status["processed_count"], status["total_target"],
                )
                await asyncio.sleep(60)
                continue

            tier, division = _SEED_TIERS[_tier_idx % len(_SEED_TIERS)]

            async with httpx.AsyncClient(timeout=15.0) as client:
                async with _sem:
                    try:
                        if division is None:
                            data = await _riot_get(
                                client,
                                f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4"
                                f"/masterleagues/by-queue/RANKED_SOLO_5x5",
                            )
                            entries = data.get("entries", [])
                            for e in entries:
                                e.setdefault("tier", "MASTER")
                        else:
                            entries = await _riot_get(
                                client,
                                f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/"
                                f"RANKED_SOLO_5x5/{tier}/{division}?page={_tier_page}",
                            )
                    except Exception as exc:
                        logger.warning("Ladder fetch failed (%s %s p%d): %s", tier, division, _tier_page, exc)
                        entries = []
                await asyncio.sleep(_CALL_DELAY)

                if not entries:
                    _tier_idx += 1
                    _tier_page = 1
                    logger.debug("Ladder exhausted for %s %s – advancing tier", tier, division)
                    continue

                if division is None:
                    _tier_idx += 1
                    _tier_page = 1
                else:
                    _tier_page += 1

                status = db._get_ingestion_status_sync()
                for entry in entries[:8]:
                    puuid = entry.get("puuid")
                    if not puuid:
                        continue

                    if status["is_paused"] or status["processed_count"] >= status["total_target"]:
                        break

                    saved = await _process_player(client, puuid, entry)

                    if saved:
                        status = db._get_ingestion_status_sync()
                        logger.info(
                            "Ingestion +%d | %d / %d (%.1f%%)",
                            saved,
                            status["processed_count"],
                            status["total_target"],
                            status["processed_count"] / status["total_target"] * 100,
                        )

        except asyncio.CancelledError:
            logger.info("Ingestion worker shutting down")
            raise
        except Exception as exc:
            logger.error("Ingestion worker outer error: %s", exc)
            await asyncio.sleep(30)
