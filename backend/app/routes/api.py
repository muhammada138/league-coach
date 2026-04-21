from fastapi import APIRouter, HTTPException
import httpx
import asyncio
import itertools
from collections import Counter
from ..services.riot import (
    riot_get, get_cached_rank, get_match_timeline, 
    _compute_perf_score, _compute_diffed_lane, get_match_details
)
from ..services.groq import get_coaching_feedback, ask_coach_question
from ..state import RIOT_REGION, RIOT_ROUTING, route_cache, enriched_cache, CACHE_VERSION, get_routing, MATCH_FETCH_SEM
from ..models.requests import LiveEnrichRequest, AskRequest, WinPredictRequest
from ..services import win_predictor
from ..services import db
from .api_helpers import (
    _fetch_recent_matches, _process_match, _aggregate_games_stats,
    _generate_coaching, _build_game_summaries, NUMERIC_STATS
)

router = APIRouter()

async def backfill_if_needed(puuid: str, tier: str, division: str, lp: int, wins: int, losses: int):
    if await db.has_history(puuid):
        return
    
    # Simple backfill: Fetch last 20 games and estimate LP path
    # NOTE: This is an estimation. Real LP gain/loss depends on MMR.
    # We use americas as default for backfill unless we want to pass routing here too
    routing = RIOT_ROUTING 
    async with httpx.AsyncClient() as client:
        try:
            match_ids = await riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=20&queue=420")
            if not match_ids: return
            
            match_tasks = [riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}") for mid in match_ids]
            match_datas = await asyncio.gather(*match_tasks, return_exceptions=True)
            
            snapshots = []
            curr_lp = lp
            curr_wins = wins
            curr_losses = losses
            
            # Process newest to oldest to build the snapshots list
            # Then we'll save them.
            for match_data in match_datas:
                if isinstance(match_data, Exception): continue
                info = match_data["info"]
                p = next((p for p in info["participants"] if p["puuid"] == puuid), None)
                if not p: continue
                
                # Timestamp of the game end
                ts = int((info.get("gameEndTimestamp") or (info.get("gameCreation", 0) + info["gameDuration"] * 1000)) / 1000)
                
                # Add snapshot BEFORE this game result
                # But actually it's easier to add snapshot AFTER this game result
                # and work backwards.
                snapshots.append((puuid, tier, division, curr_lp, curr_wins, curr_losses, ts, 'RANKED_SOLO_5x5'))
                
                # Reverse the result for the next (older) game
                if p["win"]:
                    curr_lp -= 20
                    curr_wins -= 1
                else:
                    curr_lp += 17
                    curr_losses -= 1
                
                # Clamp LP
                if curr_lp < 0: curr_lp = 0
                if curr_lp > 100: curr_lp = 100 # Simplification: doesn't handle tier demotion/promotion backfill perfectly
            
            # Save all at once
            await db.record_many_lp_snapshots(snapshots)
        except Exception as e:
            print(f"Backfill failed: {e}")

@router.get("/summoner/{game_name}/{tag_line}")
async def get_summoner(game_name: str, tag_line: str, region: str = RIOT_REGION):
    routing = get_routing(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        data = await riot_get(client, url)
    return {"puuid": data["puuid"], "gameName": data["gameName"], "tagLine": data["tagLine"]}

@router.get("/profile/{puuid}")
async def get_profile(puuid: str, region: str = RIOT_REGION):
    async with httpx.AsyncClient() as client:
        summoner, entries = await asyncio.gather(
            riot_get(client, f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"),
            riot_get(client, f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
        )
    summoner_level = summoner.get("summonerLevel", 0)
    ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
    flex   = next((e for e in entries if e.get("queueType") == "RANKED_FLEX_SR"),   None)
    profile_icon_id = summoner.get("profileIconId", 0)
    def entry_data(e):
        if e is None:
            return {"tier": "UNRANKED", "division": "", "lp": 0, "wins": 0, "losses": 0}
        return {"tier": e["tier"], "division": e["rank"], "lp": e["leaguePoints"], "wins": e["wins"], "losses": e["losses"]}
    ranked_data = entry_data(ranked)
    flex_data   = entry_data(flex)

    # Fire-and-forget LP snapshot & backfill — doesn't block the response
    asyncio.create_task(db.record_lp_snapshot(
        puuid,
        ranked_data["tier"], ranked_data["division"],
        ranked_data["lp"], ranked_data["wins"], ranked_data["losses"],
        queue='RANKED_SOLO_5x5'
    ))
    asyncio.create_task(db.record_lp_snapshot(
        puuid,
        flex_data["tier"], flex_data["division"],
        flex_data["lp"], flex_data["wins"], flex_data["losses"],
        queue='RANKED_FLEX_SR'
    ))
    
    asyncio.create_task(backfill_if_needed(
        puuid,
        ranked_data["tier"], ranked_data["division"],
        ranked_data["lp"], ranked_data["wins"], ranked_data["losses"],
    ))
    return {
        "summonerLevel": summoner_level,
        "profileIconId": profile_icon_id,
        **ranked_data,
        "flex": flex_data,
    }

@router.get("/lp-history/{puuid}")
async def lp_history(puuid: str, queue: str = 'RANKED_SOLO_5x5'):
    return await db.get_lp_history(puuid, queue=queue, days=30)


@router.get("/analyze/{puuid}")
async def analyze(puuid: str, game_name: str = "Summoner", count: int = 10, region: str = RIOT_REGION):
    count = max(5, min(count, 30))
    routing = get_routing(region)
    # Versioned cache key to force logic updates
    cache_key = f"{CACHE_VERSION}:region:{region}:analyze:{puuid}:{count}"
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
    return result

@router.get("/history/{puuid}")
async def get_history(puuid: str, start: int = 0, count: int = 10, queue: int = 420, region: str = RIOT_REGION):
    count = min(count, 10)
    routing = get_routing(region)
    # Versioned cache key to force logic updates
    cache_key = f"{CACHE_VERSION}:region:{region}:history:{puuid}:{start}:{count}:{queue}"
    cached = route_cache.get(cache_key)
    if cached is not None: return cached
    async with httpx.AsyncClient(timeout=30.0) as client:
        match_ids = await riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&queue={queue}")
        if not match_ids: return []
        match_tasks = [riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{mid}") for mid in match_ids]
        match_datas = await asyncio.gather(*match_tasks, return_exceptions=True)
    games = []
    for match_id, match_data in zip(match_ids, match_datas):
        if isinstance(match_data, Exception): continue
        info = match_data["info"]
        participants = info["participants"]
        for p in participants: p["totalMinionsKilled"] = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
        player = next((p for p in participants if p["puuid"] == puuid), None)
        if player is None: continue
        minutes = info["gameDuration"] / 60
        game_duration = info["gameDuration"]
        game_end_timestamp = info.get("gameEndTimestamp") or (info.get("gameCreation", 0) + game_duration * 1000)
        cspm = round(player["totalMinionsKilled"] / minutes if minutes > 0 else 0, 2)
        player_team_id = player.get("teamId")
        all_ps = [(p, _compute_perf_score(p, participants, None, info["gameDuration"])) for p in participants]
        player_score_h = next(s for p, s in all_ps if p.get("puuid") == puuid)
        mvp_h = max([p for p in all_ps if p[0].get("win")], key=lambda x: x[1])[0].get("puuid", "") if any(p[0].get("win") for p in all_ps) else ""
        ace_h = max([p for p in all_ps if not p[0].get("win")], key=lambda x: x[1])[0].get("puuid", "") if any(not p[0].get("win") for p in all_ps) else ""
        games.append({
            "matchId": match_id, "gameEndTimestamp": game_end_timestamp, "championName": player["championName"], "teamPosition": player.get("teamPosition", "UNKNOWN"),
            "kills": player["kills"], "deaths": player["deaths"], "assists": player["assists"], "cspm": cspm, "visionScore": player["visionScore"],
            "win": player["win"], "gameDuration": info["gameDuration"], "score": player_score_h, "mvpAce": "MVP" if puuid == mvp_h else ("ACE" if puuid == ace_h else None),
            "diffedLane": _compute_diffed_lane(participants, None, info["gameDuration"]),
            "teammates": [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "tagLine": p.get("riotIdTagline", ""), "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") == player_team_id],
            "opponents": [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "tagLine": p.get("riotIdTagline", ""), "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") != player_team_id],
        })
    route_cache.set(cache_key, games)
    return games

@router.get("/match/{match_id}/scoreboard")
async def get_scoreboard(match_id: str, region: str = RIOT_REGION):
    routing = get_routing(region)
    async with httpx.AsyncClient() as client:
        data = await riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}")
    participants = sorted(data["info"]["participants"], key=lambda p: p["teamId"])
    for p in participants: p["totalMinionsKilled"] = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
    async with httpx.AsyncClient() as c2:
        ranks = await asyncio.gather(*[get_cached_rank(c2, p.get("puuid", ""), region=region) for p in participants], return_exceptions=True)
    participants_out = []
    for i, p in enumerate(participants):
        rank = ranks[i] if not isinstance(ranks[i], Exception) else "Unranked"
        perks = p.get("perks", {})
        primary_style = next((s for s in perks.get("styles", []) if s.get("description") == "primaryStyle"), {})
        sub_style = next((s for s in perks.get("styles", []) if s.get("description") == "subStyle"), {})
        primary_selections = [sel.get("perk") for sel in primary_style.get("selections", [])]
        sub_selections = [sel.get("perk") for sel in sub_style.get("selections", [])]
        stat_perks = perks.get("statPerks", {})
        participants_out.append({
            "puuid": p.get("puuid", ""), "riotIdGameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
            "riotIdTagline": p.get("riotIdTagline", ""), "championName": p["championName"],
            "champLevel": p.get("champLevel", 0),
            "teamPosition": p.get("teamPosition", "UNKNOWN"), "kills": p["kills"], "deaths": p["deaths"], "assists": p["assists"],
            "totalMinionsKilled": p["totalMinionsKilled"], "visionScore": p["visionScore"],
            "totalDamageDealtToChampions": p.get("totalDamageDealtToChampions", 0),
            "goldEarned": p.get("goldEarned", 0),
            "summoner1Id": p.get("summoner1Id", 0), "summoner2Id": p.get("summoner2Id", 0),
            "primaryPerk": primary_selections[0] if primary_selections else None,
            "primaryStyle": primary_style.get("style"),
            "primarySelections": primary_selections,
            "subStyle": sub_style.get("style"),
            "subSelections": sub_selections,
            "statPerks": [stat_perks.get("offense"), stat_perks.get("flex"), stat_perks.get("defense")],
            "win": p["win"], "teamId": p["teamId"], "gameDuration": data["info"]["gameDuration"],
            "score": _compute_perf_score(p, participants, None, data["info"]["gameDuration"]), "rank": rank,
            "items": [p.get(f"item{j}", 0) for j in range(7)],
        })
    return {"participants": participants_out, "teams": data["info"]["teams"]}

@router.get("/live/{puuid}")
async def get_live_game(puuid: str, region: str = RIOT_REGION):
    from ..services.role_identifier import assign_team_roles
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    async with httpx.AsyncClient() as client:
        try:
            data = await riot_get(client, url)
            raw = data.get("participants", [])
            blue_p = [{"championId": p.get("championId", 0), "spells": [p.get("spell1Id"), p.get("spell2Id")]} for p in raw if p.get("teamId") == 100]
            red_p  = [{"championId": p.get("championId", 0), "spells": [p.get("spell1Id"), p.get("spell2Id")]} for p in raw if p.get("teamId") == 200]
            blue_roles, red_roles = await asyncio.gather(
                assign_team_roles(blue_p),
                assign_team_roles(red_p),
            )
            all_roles = {**blue_roles, **red_roles}
            return {
                "inGame": True, "gameId": data.get("gameId"), "gameMode": data.get("gameMode", ""),
                "gameLength": data.get("gameLength", 0),
                "queueId": data.get("gameQueueConfigId", 420),
                "participants": [
                    {
                        "puuid": p.get("puuid") or "",
                        "summonerName": (p.get("riotId") or p.get("summonerName") or "Unknown").split("#")[0],
                        "tagLine": (p.get("riotId") or "").split("#")[1] if "#" in (p.get("riotId") or "") else "",
                        "teamId": p.get("teamId", 0),
                        "championId": p.get("championId", 0),
                        "spell1Id": p.get("spell1Id") or 0,
                        "spell2Id": p.get("spell2Id") or 0,
                        "assignedPosition": all_roles.get(p.get("championId", 0), "UNKNOWN"),
                    }
                    for p in raw
                ],
            }
        except HTTPException as e:
            if e.status_code in (404, 502, 503): return {"inGame": False}
            raise e

@router.post("/live-enrich")
async def live_enrich(body: LiveEnrichRequest):
    # Map live queueId → match history queue filter and rank entry type
    _RANKED_RANK_TYPE = {420: "RANKED_SOLO_5x5", 440: "RANKED_FLEX_SR"}
    rank_type = _RANKED_RANK_TYPE.get(body.queue_id, "RANKED_SOLO_5x5")
    is_ranked_queue = body.queue_id in _RANKED_RANK_TYPE
    match_queue_filter = body.queue_id

    # Global semaphore imported from state.py caps total simultaneous
    # match-detail fetches across ALL server requests.

    async def enrich_one(puuid: str):
        # We need region here from body, but LiveEnrichRequest would need updating
        # For now, we'll try to infer it or use default. 
        # Actually, let's update LiveEnrichRequest to include region.
        region = getattr(body, 'region', RIOT_REGION)
        routing = get_routing(region)
        
        cache_key = f"v7:{puuid}:{body.queue_id}:{region}"
        cached = enriched_cache.get(cache_key)
        if cached: return cached

        base = {
            "puuid": puuid, "tier": "UNRANKED", "division": "", "lp": 0,
            "wins": 0, "losses": 0, "last5": [], "avg_score": 50,
            "recent_wr": 0.5, "champ_wr_map": {}, "main_champs": [], "streak": 0,
        }
        api_failed = False
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                entries, match_ids, mastery_data, summoner_data = await asyncio.gather(
                    riot_get(client, f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
                    riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=5&queue={match_queue_filter}"),
                    riot_get(client, f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count=20"),
                    riot_get(client, f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"),
                    return_exceptions=True,
                )

                if isinstance(entries, Exception) or isinstance(match_ids, Exception):
                    api_failed = True
                    
                if not isinstance(summoner_data, Exception):
                    base.update({
                        "summonerLevel": summoner_data.get("summonerLevel", 0)
                    })
                    
                high_mastery_champs = []
                if not isinstance(mastery_data, Exception):
                    for champ_mast in mastery_data:
                        if champ_mast.get("championPoints", 0) >= 400000:
                            high_mastery_champs.append(str(champ_mast.get("championId")))

                # Rank lookup — ranked queues use the matching entry; normals fall back to solo rank as skill proxy
                if not isinstance(entries, Exception):
                    ranked = next((e for e in entries if e.get("queueType") == rank_type), None)
                    if not ranked and not is_ranked_queue:
                        ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
                    if ranked:
                        base.update({
                            "tier": ranked["tier"], "division": ranked.get("rank", ""),
                            "lp": ranked.get("leaguePoints", 0),
                            "wins": ranked.get("wins", 0), "losses": ranked.get("losses", 0),
                        })

                if not isinstance(match_ids, Exception) and match_ids:
                    # Rate-limited match detail fetches — each call acquires the shared semaphore
                    async def _fetch(mid):
                        async with MATCH_FETCH_SEM:
                            return await get_match_details(client, mid, routing)

                    match_datas = await asyncio.gather(*[_fetch(mid) for mid in match_ids], return_exceptions=True)

                    if all(isinstance(md, Exception) for md in match_datas):
                        api_failed = True

                    recent_results, champ_ids = [], []
                    champ_wr_map: dict[str, list[int]] = {}

                    for md in match_datas:
                        if isinstance(md, Exception): continue
                        if md.get("info", {}).get("gameDuration", 0) < 210:
                            continue
                        participants = md["info"]["participants"]
                        player = next((p for p in participants if p.get("puuid") == puuid), None)
                        if not player: continue

                        score = float(_compute_perf_score(player, participants, None, md["info"]["gameDuration"]))
                        won = bool(player["win"])
                        pos = player.get("teamPosition", "UNKNOWN")
                        participant_puuids = [p.get("puuid", "") for p in participants if p.get("puuid")]
                        
                        # Store objects for internal logic, but we'll export booleans for UI
                        recent_results.append({
                            "win": won, 
                            "score": round(score, 1), 
                            "matchId": md["metadata"]["matchId"], 
                            "participants": participant_puuids, 
                            "position": pos
                        })

                        cid = str(player.get("championId", ""))
                        champ_ids.append(cid)
                        if cid not in champ_wr_map:
                            champ_wr_map[cid] = [0, 0]
                        champ_wr_map[cid][1] += 1
                        if won:
                            champ_wr_map[cid][0] += 1

                    if recent_results:
                        avg_score  = round(sum(g["score"] for g in recent_results) / len(recent_results), 1)
                        recent_wr  = round(sum(1 for g in recent_results if g["win"]) / len(recent_results), 3)
                        streak = 0
                        direction = 1 if recent_results[0]["win"] else -1
                        for g in recent_results:
                            if (g["win"] and direction == 1) or (not g["win"] and direction == -1):
                                # Streak logic
                                streak += direction
                            else:
                                break
                        from collections import Counter as _Counter
                        main_champs = [cid for cid, _ in _Counter(champ_ids).most_common(3)]
                        positions = [g.get("position", "UNKNOWN") for g in recent_results if g.get("position") != "UNKNOWN"]
                        most_common_pos = _Counter(positions).most_common(1)[0][0] if positions else "UNKNOWN"
                        
                        # Export objects so frontend can show score/matchId on hover
                        ui_last5 = [{"win": g["win"], "score": g["score"], "matchId": g["matchId"]} for g in recent_results[:5]]
                        
                        # -- Smurf Detection --
                        # Rules: Level < 80, Overall WR > 60%, and Recent Performance > 60
                        lvl = base.get("summonerLevel", 300)
                        total_games = base.get("wins", 0) + base.get("losses", 0)
                        overall_wr = (base.get("wins", 0) / total_games) if total_games > 10 else 0.5
                        
                        is_smurf = False
                        smurf_reason = ""
                        
                        if lvl < 80:
                            if overall_wr > 0.62:
                                is_smurf = True
                                smurf_reason = "Low level / High WR"
                            elif avg_score > 70:
                                is_smurf = True
                                smurf_reason = "Low level / Dominant Form"

                        base.update({
                            "last5": ui_last5, 
                            "last5_details": recent_results[:5], # Full data for internal duo-detection
                            "avg_score": avg_score,
                            "recent_wr": recent_wr,
                            "champ_wr_map": champ_wr_map,
                            "main_champs": main_champs,
                            "high_mastery_champs": high_mastery_champs,
                            "streak": streak,
                            "most_common_position": most_common_pos,
                            "is_smurf": is_smurf,
                            "smurf_reason": smurf_reason
                        })
        except Exception:
            api_failed = True
            
        if not api_failed:
            enriched_cache.set(cache_key, base)
        return base

    results = await asyncio.gather(*[enrich_one(p) for p in body.puuids[:10]])
    
    # --- Duo Detection (participant-level) ---
    # For each player, their last5 now stores match_participants (all PUUIDs who played in that match).
    # We cross-reference: for each live-game PUUID-pair, count how many matches they share
    # across ALL fetched match data — even if the match is only in ONE player's history.
    live_puuids = {r["puuid"] for r in results if r.get("puuid")}
    
    # Track unique shared matchIds per pair — a set so each game counts exactly once
    # even if it appears in both players' histories.
    pair_match_sets = {}  # {(puuid_a, puuid_b): set of matchIds}
    match_outcomes = {}   # (puuid, matchId) -> win
    for r in results:
        p_puuid = r["puuid"]
        if not p_puuid: continue
        for g in r.get("last5_details", []):
            match_participants = g.get("participants", [])
            match_id = g.get("matchId", "")
            if not match_id:
                continue
            
            match_outcomes[(p_puuid, match_id)] = g.get("win", False)
            
            for other_puuid in match_participants:
                if other_puuid != p_puuid and other_puuid in live_puuids:
                    pair = tuple(sorted([p_puuid, other_puuid]))
                    if pair not in pair_match_sets:
                        pair_match_sets[pair] = set()
                    pair_match_sets[pair].add(match_id)

    # Build an adjacency list for connected components (parties)
    adj = {p: set() for p in live_puuids}
    for pair, match_ids in pair_match_sets.items():
        if len(match_ids) >= 2:  # 2+ distinct shared games = genuine premade
            p1, p2 = pair
            adj[p1].add(p2)
            adj[p2].add(p1)
            
    duo_groups = {}
    next_gid = 1
    visited = set()
    for p in live_puuids:
        if p not in visited and adj[p]:
            # BFS to find all connected party members
            q = [p]
            component = []
            while q:
                curr = q.pop(0)
                if curr not in visited:
                    visited.add(curr)
                    component.append(curr)
                    q.extend(list(adj[curr]))
            
            if len(component) > 1:
                # Calculate shared stats for this component
                # Intersect match sets of all pairs in the component
                shared_matches = None
                for p1, p2 in itertools.combinations(sorted(component), 2):
                    m_set = pair_match_sets.get((p1, p2), set())
                    if shared_matches is None:
                        shared_matches = m_set.copy()
                    else:
                        shared_matches &= m_set
                
                if shared_matches is None: shared_matches = set()
                
                shared_total = len(shared_matches)
                shared_wr = 0
                label = "Premade"
                
                if shared_total > 0:
                    shared_wins = 0
                    for mid in shared_matches:
                        # Find any member who has this match outcome recorded
                        for m in component:
                            if (m, mid) in match_outcomes:
                                if match_outcomes[(m, mid)]:
                                    shared_wins += 1
                                break
                    shared_wr = (shared_wins / shared_total) * 100
                    
                    label = "Solid Duo"
                    if shared_wr > 65 and shared_total >= 3:
                        label = "Terror Duo"
                    elif 55 <= shared_wr <= 65:
                        label = "Synergy Found"
                    elif shared_wr < 45:
                        label = "Learning Phase"
                
                for member in component:
                    duo_groups[member] = {
                        "gid": next_gid,
                        "wr": round(shared_wr, 1),
                        "label": label
                    }
                next_gid += 1
            
    # Inject duo info back into results
    for r in results:
        info = duo_groups.get(r["puuid"])
        if info:
            r["duo_group"] = info["gid"]
            r["duo_wr"] = info["wr"]
            r["duo_label"] = info["label"]
        else:
            r["duo_group"] = 0

    return {r["puuid"]: r for r in results}

@router.post("/win-predict")
async def win_predict(body: WinPredictRequest):
    participants = [p.model_dump() for p in body.participants]
    return await win_predictor.predict(participants, body.live_stats)

@router.get("/ingest/status")
async def ingest_status():
    return await db.get_ingestion_status()


@router.post("/ingest/toggle")
async def ingest_toggle():
    return await db.toggle_ingestion()


@router.post("/admin/retrain")
async def admin_retrain():
    """Trigger ML model retraining and return accuracy stats."""
    return win_predictor.retrain_on_real_data()


@router.get("/admin/data-summary")
async def admin_data_summary():
    from ..services.meta_scraper import get_meta_data, _CHAMP_ID_MAP, is_sync_active, is_sync_paused, get_sync_mode
    from ..services.db import get_ingestion_status
    import sqlite3
    from ..state import DB_PATH

    ingest = await get_ingestion_status()
    meta = get_meta_data()
    
    # Build a reverse map for the frontend: ID -> Name
    champ_names = {str(v): k.capitalize() for k, v in _CHAMP_ID_MAP.items()}

    match_count = 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            match_count = conn.execute("SELECT COUNT(*) FROM training_matches").fetchone()[0]
    except Exception:
        pass

    # Pick any available rank for the count
    ranks_data = meta.get("data", {})
    total_champs = 0
    if ranks_data:
        all_cids = set()
        for r_data in ranks_data.values():
            all_cids.update(r_data.get("champions", {}).keys())
        total_champs = len(all_cids)
    
    return {
        "ingestion": ingest,
        "champ_names": champ_names,
        "meta": {
            "updated_at": meta.get("updated_at"),
            "ranks": list(ranks_data.keys()),
            "champion_count": total_champs,
            "details": ranks_data,
            "active": is_sync_active(),
            "paused": is_sync_paused(),
            "mode": get_sync_mode()
        },
        "training": {
            "match_count": match_count
        }
    }

@router.post("/admin/sync-meta")
async def admin_sync_meta(mode: str = "full"):
    from ..services.meta_scraper import sync_meta
    asyncio.create_task(sync_meta(mode))
    return {"ok": True, "message": f"Meta sync ({mode}) started in background"}

@router.post("/admin/cancel-sync")
async def admin_cancel_sync():
    from ..services.meta_scraper import cancel_sync
    success = cancel_sync()
    return {"ok": success, "message": "Cancel requested" if success else "No active sync"}

@router.get("/admin/sync-status")
async def admin_sync_status():
    from ..services.meta_scraper import is_sync_active, is_sync_paused
    return {
        "active": is_sync_active(),
        "paused": is_sync_paused()
    }

@router.post("/admin/toggle-sync-pause")
async def admin_toggle_sync_pause():
    from ..services.meta_scraper import toggle_pause
    new_state = toggle_pause()
    return {"ok": True, "paused": new_state}


@router.post("/admin/cleanup")
async def admin_cleanup():
    from ..services.db import cleanup_stale_data
    counts = cleanup_stale_data()
    return {"ok": True, "counts": counts}

@router.get("/match/{match_id}/timeline/{puuid}")
async def get_player_build(match_id: str, puuid: str, region: str = RIOT_REGION):
    routing = get_routing(region)
    cache_key = f"build:{routing}:{match_id}:{puuid}"
    cached = route_cache.get(cache_key)
    if cached:
        return cached

    async with httpx.AsyncClient(timeout=30.0) as client:
        data = await riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")

    participants = data.get("metadata", {}).get("participants", [])
    participant_id = next((i + 1 for i, p in enumerate(participants) if p == puuid), None)
    if participant_id is None:
        raise HTTPException(status_code=404, detail="Player not found in timeline")

    frames = data.get("info", {}).get("frames", [])
    items_purchased = []
    skill_order = []

    for frame in frames:
        ts_min = round(frame.get("timestamp", 0) / 60000, 1)
        for event in frame.get("events", []):
            if event.get("participantId") != participant_id:
                continue
            etype = event.get("type")
            if etype == "ITEM_PURCHASED":
                items_purchased.append({"itemId": event["itemId"], "ts": ts_min})
            elif etype == "ITEM_UNDO":
                undo_id = event.get("beforeId") or event.get("itemId")
                for i in range(len(items_purchased) - 1, -1, -1):
                    if items_purchased[i]["itemId"] == undo_id and not items_purchased[i].get("sold"):
                        items_purchased.pop(i)
                        break
            elif etype == "ITEM_SOLD":
                sold_id = event.get("itemId")
                for i in range(len(items_purchased) - 1, -1, -1):
                    if items_purchased[i]["itemId"] == sold_id and not items_purchased[i].get("sold"):
                        items_purchased[i]["sold"] = True
                        break
            elif etype == "SKILL_LEVEL_UP":
                slot = event.get("skillSlot")
                skill_order.append({1: "Q", 2: "W", 3: "E", 4: "R"}.get(slot, "?"))

    result = {"items": items_purchased, "skillOrder": skill_order}
    route_cache.set(cache_key, result)
    return result


@router.get("/mastery/{puuid}")
async def get_champion_mastery(puuid: str, region: str = RIOT_REGION):
    cache_key = f"mastery:{region}:{puuid}"
    cached = route_cache.get(cache_key)
    if cached:
        return cached
    async with httpx.AsyncClient(timeout=10.0) as client:
        data = await riot_get(client, f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count=20")
    route_cache.set(cache_key, data)
    return data


@router.post("/ask")
async def ask_coach(body: AskRequest):
    system_prompt = (
        f"You are a League of Legends coach. Be casual, direct, human. Bold stats. 2-3 sentences max.\n"
        f"Always reference champion abilities by key (Q, W, E, R, Passive) — never use the ability's actual name. "
        f"Make tips specific to the champion's actual kit and how it enables their win conditions.\n\n"
        f"Player context:\n{body.context}"
    )
    history = [{"role": m.role, "content": m.content} for m in body.history]
    answer = await ask_coach_question(system_prompt, history, body.question)
    return {"answer": answer}
