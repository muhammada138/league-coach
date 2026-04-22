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

Feature vector per player (9-dim):
  [rank_score, season_wr, form_score, 0.5, 0.5, 0.0, 0.0, meta_wr, matchup_adv]

Rate limiting
-------------
Shared proactive sliding-window limiter (services/rate_limiter.py) — auto-detected
from Riot response headers. Dev key: 20 req/1s, 100 req/120s. Bursts are allowed
up to the per-second limit; the limiter sleeps only when a window is full.
All routes + ingestion share the same limiter so they can't collectively exceed quota.
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
from ..services.rate_limiter import acquire as _rl_acquire, update_from_response as _rl_update

logger = logging.getLogger(__name__)

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
    # 1. Check in-memory cache
    item = _rank_cache.get(puuid)
    if item and (_time.time() - item[1]) < _RANK_TTL:
        return True, item[0]
    
    # 2. Check persistent database cache
    db_cached = db.get_enriched_profile(puuid)
    if db_cached:
        data, ts = db_cached
        # Only use if reasonably fresh (24h)
        if (_time.time() - ts) < 86400:
            # Map database keys to ingestion keys (rank <-> division)
            if "division" in data and "rank" not in data:
                data["rank"] = data["division"]
            if "lp" in data and "leaguePoints" not in data:
                data["leaguePoints"] = data["lp"]
            return True, data

    return False, None


def _rank_cache_set(puuid: str, entry: dict | None) -> None:
    _rank_cache[puuid] = (entry, _time.time())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _riot_get(client: httpx.AsyncClient, url: str):
    """Riot GET using the shared proactive rate limiter. Raises on non-200."""
    for attempt in range(3):
        await _rl_acquire()
        response = await client.get(url, headers=RIOT_HEADERS)
        _rl_update(response)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            from ..state import set_rate_limited
            set_rate_limited(retry_after + 2)
            
            banner = "\n" + "!"*60 + "\n" + "!!! 🛑 RIOT RATE LIMIT (429) DETECTED !!!".center(60) + "\n" + f"!!! Sleeping {retry_after + 2}s (attempt {attempt + 1}) !!!".center(60) + "\n" + "!"*60
            logger.warning(banner)
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


from .meta_scraper import sync_meta, get_meta_data

# ... (rest of imports) ...

def _player_feats(rank_entry: dict | None, form: float = 0.5, champion_id: int = 0, lobby_rank: str = "emerald", opp_id: int = 0, role: str = "all") -> list[float]:
    """9-dim feature vector. meta stats added from Lolalytics."""
    rank_score, season_wr = _rank_score_from_entry(rank_entry)
    
    meta = get_meta_data()
    rank_key = lobby_rank.lower()
    rank_meta = meta.get("data", {}).get(rank_key, {})
    champs = rank_meta.get("champions", {})
    
    # Map role to Lolalytics lane key
    role_map = {
        "TOP": "top",
        "JUNGLE": "jungle",
        "MIDDLE": "middle",
        "BOTTOM": "bottom",
        "UTILITY": "support"
    }
    lane_key = role_map.get(role.upper(), "all")
    
    cid_str = f"{champion_id}:{lane_key}"
    champ_meta = champs.get(cid_str, {})
    if not champ_meta and lane_key != "all":
        # Fallback to 'all' if specific lane data is missing
        champ_meta = champs.get(f"{champion_id}:all", {})
        
    meta_wr = champ_meta.get("wr", 50.0) / 100.0
    
    matchup_adv = 0.5
    if opp_id:
        # Matchup WR is vsWr in champ_meta['matchups'][opp_id]
        matchups = champ_meta.get("matchups", {})
        opp_stat = matchups.get(str(opp_id), {})
        matchup_wr = opp_stat.get("wr")
        if matchup_wr:
            matchup_adv = float(matchup_wr) / 100.0

    return [rank_score, season_wr, form, 0.5, 0.5, 0.0, 0.0, meta_wr, matchup_adv]


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
    try:
        match_ids = await _riot_get(
            client,
            f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?count=10&queue=420",
        )
    except Exception as exc:
        logger.debug("Match IDs failed for %.12s: %s", puuid, exc)
        return 0

    # Step 2: Fetch match details for all new matches — Parallelized (Semaphore 10)
    status = db._get_ingestion_status_sync()
    if status["is_paused"] or status["processed_count"] >= status["total_target"]:
        return 0

    new_mids = [mid for mid in match_ids if not await db.has_training_match(mid)]
    if not new_mids: return 0

    sem = asyncio.Semaphore(10) # Prevent burst socket exhaustion

    async def _fetch_detail(mid):
        async with sem:
            try:
                return mid, await _riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}")
            except Exception: return mid, None

    detail_results = await asyncio.gather(*[_fetch_detail(mid) for mid in new_mids])
    match_details: dict[str, dict] = {mid: data for mid, data in detail_results if data}

    if not match_details:
        return 0

    # Step 3: Collect all unique non-seed PUUIDs across all fetched matches
    other_puuids: set[str] = set()
    for data in match_details.values():
        for p in data["info"]["participants"]:
            uid = p.get("puuid")
            if uid and uid != puuid:
                other_puuids.add(uid)

    # Step 4: Resolve rank for every unique non-seed participant — Parallelized (Semaphore 10)
    _rank_cache_set(puuid, seed_rank_entry)
    rank_cache: dict[str, dict | None] = {puuid: seed_rank_entry}
    uncached_puuids = []

    for other_puuid in other_puuids:
        hit, cached_entry = _rank_cache_get(other_puuid)
        if hit:
            rank_cache[other_puuid] = cached_entry
        else:
            uncached_puuids.append(other_puuid)

    sem = asyncio.Semaphore(10)

    async def _fetch_rank(target_puuid):
        async with sem:
            try:
                entries = await _riot_get(client, f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{target_puuid}")
                entry = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
                _rank_cache_set(target_puuid, entry)
                # Also save to persistent DB so search users benefit from crawler data
                if entry:
                    db.save_enriched_profile(target_puuid, {
                        "tier": entry["tier"], "division": entry["rank"], "lp": entry["leaguePoints"],
                        "wins": entry["wins"], "losses": entry["losses"], "summonerLevel": 300 # proxy
                    })
                return target_puuid, entry
            except: 
                return target_puuid, None

    if uncached_puuids:
        rank_results = await asyncio.gather(*[_fetch_rank(u) for u in uncached_puuids])
        for target_puuid, entry in rank_results:
            rank_cache[target_puuid] = entry
            # Record LP snapshot for the graph
            if entry:
                asyncio.create_task(db.record_lp_snapshot(
                    target_puuid, 
                    entry["tier"], entry["rank"], entry["leaguePoints"], 
                    entry["wins"], entry["losses"], 
                    queue="RANKED_SOLO_5x5"
                ))

    # Step 5: Build ordered list of new match IDs (newest → oldest, API order)
    ordered = [mid for mid in match_ids if mid in match_details]

    # Step 6: Save training samples — seed player's form from older matches in batch
    saved = 0
    for i, mid in enumerate(ordered):
        status = db._get_ingestion_status_sync()
        if status["is_paused"] or status["processed_count"] >= status["total_target"]:
            break

        try:
            info         = match_details[mid]["info"]
            participants = info["participants"]
            duration     = info["gameDuration"]

            blue = [p for p in participants if p["teamId"] == 100]
            red  = [p for p in participants if p["teamId"] == 200]
            if len(blue) < 1 or len(red) < 1:
                continue

            # identify roles for meta matchup stats
            blue_p = [{"championId": p.get("championId", 0), "spells": [p.get("summoner1Id"), p.get("summoner2Id")]} for p in blue]
            red_p  = [{"championId": p.get("championId", 0), "spells": [p.get("summoner1Id"), p.get("summoner2Id")]} for p in red]
            
            from .role_identifier import assign_team_roles
            blue_roles = await assign_team_roles(blue_p)
            red_roles  = await assign_team_roles(red_p)
            
            blue_role_map = {role: cid for cid, role in blue_roles.items()}
            red_role_map  = {role: cid for cid, role in red_roles.items()}

            # Determine lobby rank (for training, we use the tier of the seed player)
            lobby_rank = (seed_rank_entry.get("tier") if seed_rank_entry else "EMERALD") or "EMERALD"

            # Compute seed player's form from chronologically PRIOR matches in this same batch.
            # ordered list is [NEWEST, ..., OLDEST]. So matches[i+1:] are older than matches[i].
            prior_matches = [match_details[m] for m in ordered[i+1:] if m in match_details]
            seed_form = _compute_seed_form(puuid, prior_matches)

            def team_vec(players: list, roles, opp_role_map) -> list[float]:
                feats = []
                for p in players:
                    cid = p.get("championId", 0)
                    role = roles.get(cid, "UNKNOWN")
                    opp_cid = opp_role_map.get(role, 0)
                    
                    f = _player_feats(
                        rank_cache.get(p.get("puuid")),
                        seed_form if p.get("puuid") == puuid else 0.5,
                        champion_id=cid,
                        lobby_rank=lobby_rank,
                        opp_id=opp_cid,
                        role=role
                    )
                    feats.append(f)
                return np.mean(feats, axis=0).tolist()

            blue_feats = team_vec(blue, blue_roles, red_role_map)
            red_feats  = team_vec(red, red_roles, blue_role_map)
            blue_won   = any(p.get("win") for p in blue)

            await db.save_training_match(mid, blue_feats, red_feats, blue_won)
            saved += 1

        except Exception as exc:
            logger.error("Feature extraction failed for %s: %s", mid, exc, exc_info=True)

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
    
    # Initial setup
    db.cleanup_stale_data()
    last_meta_sync = _time.time()
    last_cleanup = _time.time()

    while True:
        try:
            # Sync meta and cleanup daily
            now = _time.time()
            # We still keep the periodic auto-sync but remove the immediate startup trigger
            if (now - last_meta_sync) > 86400:
                asyncio.create_task(sync_meta())
                last_meta_sync = now
            
            if (now - last_cleanup) > 86400:
                db.cleanup_stale_data()
                last_cleanup = now

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
                is_paused = status["is_paused"]
                processed_count = status["processed_count"]
                total_target = status["total_target"]

                for entry in entries[:8]:
                    puuid = entry.get("puuid")
                    if not puuid:
                        continue

                    if is_paused or processed_count >= total_target:
                        break

                    saved = await _process_player(client, puuid, entry)

                    if saved:
                        processed_count += saved
                        # Re-read pause state so a mid-loop toggle takes effect immediately
                        _s = db._get_ingestion_status_sync()
                        is_paused = _s["is_paused"]
                        logger.info(
                            "Ingestion +%d | %d / %d (%.1f%%)",
                            saved,
                            processed_count,
                            total_target,
                            processed_count / total_target * 100,
                        )

        except asyncio.CancelledError:
            logger.info("Ingestion worker shutting down")
            raise
        except Exception as exc:
            logger.error("Ingestion worker outer error: %s", exc)
            await asyncio.sleep(30)
