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
    if not force:
        cached = db.get_enriched_profile(puuid)
        if cached:
            data, ts = cached
            if "games" in data:
                data["last_updated"] = ts
                return data
    count = max(5, min(count, 30))
    routing = get_routing(region)
    cache_key = f"{CACHE_VERSION}:region:{region}:analyze:{puuid}:{count}"
    if not force:
        cached = route_cache.get(cache_key)
        if cached is not None: return cached

    async with httpx.AsyncClient(timeout=30.0) as client:
        match_ids, queue_used, match_datas = await _fetch_recent_matches(client, puuid, routing, count)

        games = []
        for match_id, match_data in zip(match_ids, match_datas):
            if isinstance(match_data, Exception): continue

            processed = _process_match(match_id, match_data, puuid)
            if processed:
                games.append(processed)

    if not games: raise HTTPException(status_code=404, detail="Could not process any matches")

    stats = _aggregate_games_stats(games)
    coaching = await _generate_coaching(game_name, stats, games=games)
    game_summaries, most_diffed_lane = _build_game_summaries(games)
    
    result = {
        "gameName": game_name, "queueUsed": queue_used, "mostPlayedPosition": stats["most_common_position"], "winRate": stats["win_rate"],
        "mostDiffedLane": most_diffed_lane, "playerAverages": {stat: round(stats["player_avgs"][stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(stats["player_cspm"], 2), "kda": round(stats["player_kda"], 2)},
        "lobbyAverages": {stat: round(stats["lobby_avgs_agg"][stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(stats["lobby_cspm"], 2), "kda": round(stats["lobby_kda"], 2)},
        "deltas": {stat: round(stats["player_avgs"][stat] - stats["lobby_avgs_agg"][stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(stats["player_cspm"] - stats["lobby_cspm"], 2), "kda": round(stats["player_kda"] - stats["lobby_kda"], 2)},
        "coaching": coaching, "games": game_summaries, "champStats": stats.get("champ_stats", {}),
    }
    route_cache.set(cache_key, result)
    db.save_enriched_profile(puuid, result)
    return result
