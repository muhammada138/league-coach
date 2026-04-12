"""
ML Data Ingestion Worker — accumulates real match data for win predictor retraining.

Strategy
--------
Cycles through GOLD/PLATINUM/DIAMOND league ladder pages. For each player it
fetches rank + last 10 ranked match IDs + each match detail, then extracts a
7-dim feature vector per participant and saves
(blue_feats, red_feats, blue_won) to the training_matches table.

Feature extraction
------------------
For the seed player (whose rank we fetched): all features from API data.
For the other 9 participants: form_score from match data, neutral (0.5) for
rank/WR fields — real form data is more valuable than random synthetic.

Rate limiting
-------------
Semaphore(1) + 2 s sleep between every Riot API call ≈ 30 req/min.
Dev-key budget: 50 req/min (100 per 2 min).  30 + normal app usage ≈ safe.
The worker checks is_paused from DB before every call and sleeps if set.
"""

import asyncio
import logging

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

# One request at a time — no burst
_sem = asyncio.Semaphore(1)

# Seconds to sleep after every successful Riot request
_CALL_DELAY = 1.25

# Ladder tiers cycled in order; restarts from the top when exhausted
_SEED_TIERS = [
    ("GOLD",     "I"),
    ("PLATINUM", "I"),
    ("DIAMOND",  "IV"),
    ("GOLD",     "II"),
    ("PLATINUM", "II"),
    ("DIAMOND",  "III"),
    ("GOLD",     "III"),
    ("PLATINUM", "III"),
    ("SILVER",   "I"),
]

# Mutable state — survives across loop iterations, resets on restart (ok: dedup by match_id)
_tier_idx  = 0
_tier_page = 1


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


def _player_feats(
    p: dict,
    all_players: list,
    game_duration: int,
    rank_entry: dict | None,
) -> list[float]:
    """
    7-dim feature vector for one match participant.
    rank_entry: the player's LeagueEntry if available, else None → neutral rank/WR.
    """
    form = float(_compute_perf_score(p, all_players, None, game_duration)) / 100.0

    if rank_entry:
        tier_val   = TIER_SCORE.get(rank_entry.get("tier", "SILVER"), 3.5)
        div_val    = DIV_BONUS.get(rank_entry.get("rank", ""), 0.0)
        lp_bonus   = (rank_entry.get("leaguePoints", 0) / 100.0) * 0.25
        rank_score = min((tier_val + div_val + lp_bonus) / MAX_RANK, 1.0)

        w = rank_entry.get("wins", 0)
        l = rank_entry.get("losses", 0)
        raw_wr    = w / (w + l) if (w + l) > 0 else 0.5
        conf      = min((w + l) / 100.0, 1.0)
        season_wr = raw_wr * conf + 0.5 * (1.0 - conf)
    else:
        rank_score = 0.5
        season_wr  = 0.5

    # recent_wr / champ_wr / mastery / streak → neutral (single-match context)
    return [rank_score, season_wr, form, 0.5, 0.5, 0.0, 0.0]


async def _process_player(
    client: httpx.AsyncClient,
    puuid: str,
    seed_rank_entry: dict | None,
) -> int:
    """
    Fetch and persist training samples from one player's recent matches.
    Returns the number of new matches saved.
    """
    status = db._get_ingestion_status_sync()
    if status["is_paused"] or status["processed_count"] >= status["total_target"]:
        return 0

    # Prefer the rank entry we already have from the ladder response; only
    # make an extra call if we don't have one (shouldn't normally happen).
    ranked = seed_rank_entry
    if not ranked:
        async with _sem:
            try:
                entries = await _riot_get(
                    client,
                    f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}",
                )
            except Exception as exc:
                logger.debug("Rank fetch failed for %.12s: %s", puuid, exc)
                entries = []
        await asyncio.sleep(_CALL_DELAY)
        ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)

    # Match IDs
    status = db._get_ingestion_status_sync()
    if status["is_paused"]:
        return 0

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

    saved = 0
    for mid in match_ids:
        status = db._get_ingestion_status_sync()
        if status["is_paused"] or status["processed_count"] >= status["total_target"]:
            break

        if db._has_training_match_sync(mid):
            continue  # already processed — skip API call entirely

        async with _sem:
            try:
                match_data = await _riot_get(
                    client,
                    f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}",
                )
            except Exception as exc:
                logger.debug("Match fetch failed %s: %s", mid, exc)
                await asyncio.sleep(_CALL_DELAY)
                continue
        await asyncio.sleep(_CALL_DELAY)

        try:
            info         = match_data["info"]
            participants = info["participants"]
            duration     = info["gameDuration"]

            blue = [p for p in participants if p["teamId"] == 100]
            red  = [p for p in participants if p["teamId"] == 200]
            if len(blue) < 1 or len(red) < 1:
                continue

            def team_vec(players: list) -> list[float]:
                feats = [
                    _player_feats(
                        p, participants, duration,
                        ranked if p.get("puuid") == puuid else None,
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
    Long-running background task.  Paused by default — resume via
    POST /ingest/toggle.  Safely handles cancellation on shutdown.
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
                # Fetch one page of ladder entries
                async with _sem:
                    try:
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
                    # Exhausted this tier/page — move to next tier
                    _tier_idx += 1
                    _tier_page = 1
                    logger.debug("Ladder exhausted for %s %s – advancing tier", tier, division)
                    continue

                _tier_page += 1

                for entry in entries[:8]:   # process 8 players per ladder page
                    puuid = entry.get("puuid")
                    if not puuid:
                        continue

                    status = db._get_ingestion_status_sync()
                    if status["is_paused"] or status["processed_count"] >= status["total_target"]:
                        break

                    saved = await _process_player(client, puuid, entry)

                    if saved:
                        s = db._get_ingestion_status_sync()
                        logger.info(
                            "Ingestion +%d | %d / %d (%.1f%%)",
                            saved,
                            s["processed_count"],
                            s["total_target"],
                            s["processed_count"] / s["total_target"] * 100,
                        )

        except asyncio.CancelledError:
            logger.info("Ingestion worker shutting down")
            raise
        except Exception as exc:
            logger.error("Ingestion worker outer error: %s", exc)
            await asyncio.sleep(30)
