import asyncio
import time
import httpx
from fastapi import APIRouter, HTTPException

from ..services import db
from ..state import (
    RIOT_REGION, route_cache, 
    CACHE_VERSION, get_routing
)
from .api_helpers import (
    _fetch_recent_matches, _process_match, _aggregate_games_stats,
    _generate_coaching, _build_game_summaries, NUMERIC_STATS
)

router = APIRouter(tags=["Analysis"])

@router.get("/analyze/{puuid}")
async def analyze(puuid: str, game_name: str = "Summoner", count: int = 10, region: str = RIOT_REGION, force: bool = False):
    count = max(5, min(count, 30))
    routing = get_routing(region)
    cache_key = f"{CACHE_VERSION}:region:{region}:analyze:{puuid}:{count}"
    
    # 1. Tier 1 Cache: In-memory (Fastest, survives for 1 hour now)
    if not force:
        cached = route_cache.get(cache_key)
        if cached is not None: 
            return cached

    # 2. Tier 2 Cache: Persistent DB (Survives server restarts)
    if not force:
        cached_db = db.get_enriched_profile(puuid)
        if cached_db:
            data, ts = cached_db
            # Use DB cache if it contains games and is less than 30 mins old
            # OR if it's exactly the same count requested
            if "games" in data and (time.time() - ts < 1800):
                # Only return if it actually has the number of games we need
                if len(data.get("games", [])) >= count:
                    data["last_updated"] = ts
                    # Save to memory cache for next time
                    route_cache.set(cache_key, data)
                    return data

    async with httpx.AsyncClient(timeout=30.0) as client:
        # This fetches IDs (prioritized) and then detail payloads in parallel
        match_ids, queue_used, match_datas = await _fetch_recent_matches(client, puuid, routing, count)

        # 3. Parallel Process Matches (CPU-bound math)
        # Using to_thread to keep the event loop free while calculating 100+ player scores
        async def _async_process(mid, mdata):
            return await asyncio.to_thread(_process_match, mid, mdata, puuid)

        process_tasks = []
        for mid, mdata in zip(match_ids, match_datas):
            if isinstance(mdata, Exception) or not mdata: continue
            process_tasks.append(_async_process(mid, mdata))
        
        games = await asyncio.gather(*process_tasks)
        games = [g for g in games if g is not None]

    if not games: raise HTTPException(status_code=404, detail="Could not process any matches")

    # 4. Aggregate & AI Coaching
    stats = _aggregate_games_stats(games)
    coaching = await _generate_coaching(game_name, stats, games=games)
    game_summaries, most_diffed_lane = _build_game_summaries(games)
    
    result = {
        "gameName": game_name, 
        "queueUsed": queue_used, 
        "mostPlayedPosition": stats["most_common_position"], 
        "winRate": stats["win_rate"],
        "mostDiffedLane": most_diffed_lane, 
        "playerAverages": {stat: round(stats["player_avgs"][stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(stats["player_cspm"], 2), "kda": round(stats["player_kda"], 2)},
        "lobbyAverages": {stat: round(stats["lobby_avgs_agg"][stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(stats["lobby_cspm"], 2), "kda": round(stats["lobby_kda"], 2)},
        "deltas": {stat: round(stats["player_avgs"][stat] - stats["lobby_avgs_agg"][stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(stats["player_cspm"] - stats["lobby_cspm"], 2), "kda": round(stats["player_kda"] - stats["lobby_kda"], 2)},
        "coaching": coaching, 
        "games": game_summaries, 
        "champStats": stats.get("champ_stats", {}),
    }

    # 5. Populate Caches
    route_cache.set(cache_key, result)
    db.save_enriched_profile(puuid, result)
    
    return result
