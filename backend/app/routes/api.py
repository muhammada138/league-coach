from fastapi import APIRouter, HTTPException, Depends
import httpx
import asyncio
from collections import Counter
from typing import List
from ..services.riot import (
    riot_get, get_cached_rank, get_match_timeline, 
    _compute_perf_score, _compute_diffed_lane
)
from ..services.groq import get_coaching_feedback, ask_coach_question
from ..state import RIOT_REGION, RIOT_ROUTING, route_cache, enriched_cache, CACHE_VERSION, get_routing
from ..models.requests import LiveEnrichRequest, AskRequest, WinPredictRequest
from ..services import win_predictor
from ..services import db

router = APIRouter()

NUMERIC_STATS = [
    "kills", "deaths", "assists", "totalMinionsKilled",
    "visionScore", "totalDamageDealtToChampions", "goldEarned",
    "wardsPlaced", "wardsKilled",
]

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
                snapshots.append((puuid, tier, division, curr_lp, curr_wins, curr_losses, ts))
                
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
        queue_priorities = [420, 440, 400]
        id_tasks = [
            riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}&queue={q}")
            for q in queue_priorities
        ]
        id_results = await asyncio.gather(*id_tasks, return_exceptions=True)
        match_ids = []
        queue_used = 420
        for q, ids in zip(queue_priorities, id_results):
            if isinstance(ids, list) and ids:
                match_ids = ids
                queue_used = q
                break
        if not match_ids: raise HTTPException(status_code=404, detail="No matches found")
        match_tasks = [riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{mid}") for mid in match_ids]
        match_datas = await asyncio.gather(*match_tasks, return_exceptions=True)
        games = []
        for match_id, match_data in zip(match_ids, match_datas):
            if isinstance(match_data, Exception): continue
            info = match_data["info"]
            participants = info["participants"]
            for p in participants:
                p["totalMinionsKilled"] = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
            game_duration = info["gameDuration"]
            game_end_timestamp = info.get("gameEndTimestamp") or (info.get("gameCreation", 0) + game_duration * 1000)
            player = next((p for p in participants if p["puuid"] == puuid), None)
            if player is None: continue
            player_stats = {
                "championName": player["championName"],
                "teamPosition": player.get("teamPosition", "UNKNOWN"),
                "kills": player["kills"],
                "deaths": player["deaths"],
                "assists": player["assists"],
                "totalMinionsKilled": player["totalMinionsKilled"],
                "visionScore": player["visionScore"],
                "totalDamageDealtToChampions": player["totalDamageDealtToChampions"],
                "goldEarned": player["goldEarned"],
                "damageDealtToTurrets": player["damageDealtToTurrets"],
                "wardsPlaced": player["wardsPlaced"],
                "wardsKilled": player["wardsKilled"],
                "win": player["win"],
                "gameDuration": game_duration,
            }
            lobby_avgs = {stat: sum(p[stat] for p in participants) / len(participants) for stat in NUMERIC_STATS}
            deltas = {stat: player_stats[stat] - lobby_avgs[stat] for stat in NUMERIC_STATS}
            minutes = game_duration / 60
            player_cspm = player_stats["totalMinionsKilled"] / minutes if minutes > 0 else 0
            lobby_cspm = lobby_avgs["totalMinionsKilled"] / minutes if minutes > 0 else 0
            all_player_scores = [(p, _compute_perf_score(p, participants, None, game_duration)) for p in participants]
            game_score = next(s for p, s in all_player_scores if p.get("puuid") == puuid)
            game_diffed_lane = _compute_diffed_lane(participants, None, game_duration)
            winning_scores = [(p, s) for p, s in all_player_scores if p.get("win")]
            losing_scores  = [(p, s) for p, s in all_player_scores if not p.get("win")]
            mvp_puuid_g = max(winning_scores, key=lambda x: x[1])[0].get("puuid") if winning_scores else None
            ace_puuid_g = max(losing_scores,  key=lambda x: x[1])[0].get("puuid") if losing_scores  else None
            mvp_ace = "MVP" if puuid == mvp_puuid_g else ("ACE" if puuid == ace_puuid_g else None)
            player_team_id = player.get("teamId")
            teammates = [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "tagLine": p.get("riotIdTagline", ""), "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") == player_team_id]
            opponents = [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "tagLine": p.get("riotIdTagline", ""), "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") != player_team_id]
            games.append({
                "matchId": match_id, "gameEndTimestamp": game_end_timestamp, "playerStats": player_stats, "lobbyAverages": lobby_avgs,
                "deltas": deltas, "playerCspm": round(player_cspm, 2), "lobbyCspm": round(lobby_cspm, 2), "score": game_score,
                "diffedLane": game_diffed_lane, "mvpAce": mvp_ace, "teammates": teammates, "opponents": opponents,
            })
    if not games: raise HTTPException(status_code=404, detail="Could not process any matches")
    n = len(games)
    player_avgs = {stat: sum(g["playerStats"][stat] for g in games) / n for stat in NUMERIC_STATS}
    lobby_avgs_agg = {stat: sum(g["lobbyAverages"][stat] for g in games) / n for stat in NUMERIC_STATS}
    overall_deltas = {stat: player_avgs[stat] - lobby_avgs_agg[stat] for stat in NUMERIC_STATS}
    total_seconds = sum(g["playerStats"]["gameDuration"] for g in games)
    total_minutes = total_seconds / 60
    player_cspm = player_avgs["totalMinionsKilled"] / (total_minutes / n) if total_minutes > 0 else 0
    lobby_cspm = lobby_avgs_agg["totalMinionsKilled"] / (total_minutes / n) if total_minutes > 0 else 0
    player_kda = (player_avgs["kills"] + player_avgs["assists"]) / max(player_avgs["deaths"], 1)
    lobby_kda = (lobby_avgs_agg["kills"] + lobby_avgs_agg["assists"]) / max(lobby_avgs_agg["deaths"], 1)
    wins = sum(1 for g in games if g["playerStats"]["win"])
    win_rate = round((wins / n) * 100, 1)
    positions = [g["playerStats"]["teamPosition"] for g in games]
    most_common_position = Counter(positions).most_common(1)[0][0]
    champ_names = [g["playerStats"]["championName"] for g in games]
    most_played_champ = Counter(champ_names).most_common(1)[0][0]
    champ_counter = Counter(champ_names)
    champ_wins = Counter(g["playerStats"]["championName"] for g in games if g["playerStats"]["win"])
    champ_breakdown = ", ".join(
        f"{champ} ({champ_wins.get(champ, 0)}W/{count - champ_wins.get(champ, 0)}L)"
        for champ, count in champ_counter.most_common()
    )

    # Groq Logic
    system_prompt = (
        "You are a League of Legends coach giving direct, personal feedback to this specific player. "
        "Always speak in second person: 'you', 'your', 'you're'. Talk like a real coach, not a report writer. "
        "Be blunt and human. No corporate filler. Give 3-4 weaknesses where they are underperforming vs their lobby. "
        "Each tip: 1-2 sentences max. Lead with the problem, end with one concrete fix. "
        "Bold (**) every stat number and every key concept/stat name. "
        f"The player is mainly playing **{most_played_champ}** — reference this champion's specific kit, "
        "abilities, and win conditions in your tips. If they play multiple champions, tailor advice to each "
        "champion's unique strengths and how to leverage them to improve the weak stats. "
        "FORMATTING RULES: Start each tip with a number and a period (e.g., '1. ', '2. '). "
        "Each numbered tip must be on its own new line. No intro sentence."
    )
    user_prompt = (
        f"Player: {game_name}\n"
        f"Champions played: {champ_breakdown}\n"
        f"Most played role: {most_common_position}\n"
        f"Win rate last {n} games: {win_rate}%\n\n"
        f"Player averages vs lobby averages:\n"
        f"- KDA: {player_kda:.2f} vs {lobby_kda:.2f}\n"
        f"- CSPM: {player_cspm:.2f} vs {lobby_cspm:.2f}\n"
        f"- Vision score: {player_avgs['visionScore']:.1f} vs {lobby_avgs_agg['visionScore']:.1f}\n"
        f"- Damage dealt: {player_avgs['totalDamageDealtToChampions']:.0f} vs {lobby_avgs_agg['totalDamageDealtToChampions']:.0f}\n"
        f"- Gold earned: {player_avgs['goldEarned']:.0f} vs {lobby_avgs_agg['goldEarned']:.0f}\n"
        f"- Wards placed: {player_avgs['wardsPlaced']:.1f} vs {lobby_avgs_agg['wardsPlaced']:.1f}\n"
        f"- Wards killed: {player_avgs['wardsKilled']:.1f} vs {lobby_avgs_agg['wardsKilled']:.1f}"
    )
    coaching = await get_coaching_feedback(system_prompt, user_prompt)
    
    game_summaries = []
    for g in games:
        ps = g["playerStats"]
        game_summaries.append({
            "matchId": g["matchId"], "gameEndTimestamp": g["gameEndTimestamp"], "championName": ps["championName"],
            "teamPosition": ps["teamPosition"], "kills": ps["kills"], "deaths": ps["deaths"], "assists": ps["assists"],
            "cspm": g["playerCspm"], "visionScore": ps["visionScore"], "win": ps["win"], "gameDuration": ps["gameDuration"],
            "score": g["score"], "diffedLane": g["diffedLane"], "mvpAce": g.get("mvpAce"), "teammates": g.get("teammates", []), "opponents": g.get("opponents", []),
        })
    diffed_lanes = [g["diffedLane"] for g in game_summaries if g["diffedLane"] and not g["win"]]
    most_diffed_lane = Counter(diffed_lanes).most_common(1)[0][0] if diffed_lanes else None
    result = {
        "gameName": game_name, "queueUsed": queue_used, "mostPlayedPosition": most_common_position, "winRate": win_rate,
        "mostDiffedLane": most_diffed_lane, "playerAverages": {stat: round(player_avgs[stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(player_cspm, 2), "kda": round(player_kda, 2)},
        "lobbyAverages": {stat: round(lobby_avgs_agg[stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(lobby_cspm, 2), "kda": round(lobby_kda, 2)},
        "deltas": {stat: round(player_avgs[stat] - lobby_avgs_agg[stat], 2) for stat in NUMERIC_STATS} | {"cspm": round(player_cspm - lobby_cspm, 2), "kda": round(player_kda - lobby_kda, 2)},
        "coaching": coaching, "games": game_summaries,
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
        primary_perk = primary_style.get("selections", [{}])[0].get("perk") if primary_style.get("selections") else None
        sub_style = next((s for s in perks.get("styles", []) if s.get("description") == "subStyle"), {})
        participants_out.append({
            "puuid": p.get("puuid", ""), "riotIdGameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
            "riotIdTagline": p.get("riotIdTagline", ""), "championName": p["championName"],
            "champLevel": p.get("champLevel", 0),
            "teamPosition": p.get("teamPosition", "UNKNOWN"), "kills": p["kills"], "deaths": p["deaths"], "assists": p["assists"],
            "totalMinionsKilled": p["totalMinionsKilled"], "visionScore": p["visionScore"],
            "totalDamageDealtToChampions": p.get("totalDamageDealtToChampions", 0),
            "goldEarned": p.get("goldEarned", 0),
            "summoner1Id": p.get("summoner1Id", 0), "summoner2Id": p.get("summoner2Id", 0),
            "primaryPerk": primary_perk, "subStyle": sub_style.get("style"),
            "win": p["win"], "teamId": p["teamId"], "gameDuration": data["info"]["gameDuration"],
            "score": _compute_perf_score(p, participants, None, data["info"]["gameDuration"]), "rank": rank,
            "items": [p.get(f"item{j}", 0) for j in range(7)],
        })
    return {"participants": participants_out, "teams": data["info"]["teams"]}

@router.get("/live/{puuid}")
async def get_live_game(puuid: str, region: str = RIOT_REGION):
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    async with httpx.AsyncClient() as client:
        try:
            data = await riot_get(client, url)
            return {
                "inGame": True, "gameId": data.get("gameId"), "gameMode": data.get("gameMode", ""),
                "gameLength": data.get("gameLength", 0),
                "queueId": data.get("gameQueueConfigId", 420),
                "participants": [{"puuid": p.get("puuid", ""), "summonerName": (p.get("riotId") or p.get("summonerName") or "Unknown").split("#")[0], "tagLine": (p.get("riotId") or "").split("#")[1] if "#" in (p.get("riotId") or "") else "", "teamId": p.get("teamId", 0), "championId": p.get("championId", 0)} for p in data.get("participants", [])],
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

    # Single semaphore shared across all concurrent players — caps total simultaneous
    # match-detail fetches so we stay within the dev key 100 req/2 min limit.
    _match_sem = asyncio.Semaphore(8)

    async def enrich_one(puuid: str):
        # We need region here from body, but LiveEnrichRequest would need updating
        # For now, we'll try to infer it or use default. 
        # Actually, let's update LiveEnrichRequest to include region.
        region = getattr(body, 'region', RIOT_REGION)
        routing = get_routing(region)
        
        cache_key = f"v3:{puuid}:{body.queue_id}:{region}"
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
                entries, match_ids = await asyncio.gather(
                    riot_get(client, f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
                        riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=6&queue={match_queue_filter}"),
                    return_exceptions=True,
                )
                
                if isinstance(entries, Exception) or isinstance(match_ids, Exception):
                    api_failed = True

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
                        async with _match_sem:
                            return await riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{mid}")

                    match_datas = await asyncio.gather(*[_fetch(mid) for mid in match_ids], return_exceptions=True)
                    
                    if all(isinstance(md, Exception) for md in match_datas):
                        api_failed = True

                    recent_games, champ_ids = [], []
                    # champ_wr_map: {championId_str: [wins, total]}
                    champ_wr_map: dict[str, list[int]] = {}

                    for md in match_datas:
                        if isinstance(md, Exception): continue
                        
                        # Skip remakes (games under 3.5 minutes)
                        if md.get("info", {}).get("gameDuration", 0) < 210:
                            continue
                            
                        participants = md["info"]["participants"]
                        player = next((p for p in participants if p.get("puuid") == puuid), None)
                        if not player: continue

                        score = float(_compute_perf_score(player, participants, None, md["info"]["gameDuration"]))
                        won = bool(player["win"])
                        participant_puuids = [p.get("puuid", "") for p in participants if p.get("puuid")]
                        recent_games.append({"win": won, "score": round(score, 1), "matchId": md["metadata"]["matchId"], "participants": participant_puuids})

                        cid = str(player.get("championId", ""))
                        champ_ids.append(cid)
                        if cid not in champ_wr_map:
                            champ_wr_map[cid] = [0, 0]
                        champ_wr_map[cid][1] += 1
                        if won:
                            champ_wr_map[cid][0] += 1

                    if recent_games:
                        avg_score  = round(sum(g["score"] for g in recent_games) / len(recent_games), 1)
                        recent_wr  = round(sum(1 for g in recent_games if g["win"]) / len(recent_games), 3)
                        streak = 0
                        direction = 1 if recent_games[0]["win"] else -1
                        for g in recent_games:
                            if (g["win"] and direction == 1) or (not g["win"] and direction == -1):
                                streak += direction
                            else:
                                break
                        from collections import Counter as _Counter
                        main_champs = [cid for cid, _ in _Counter(champ_ids).most_common(3)]
                        base.update({
                            "last5": recent_games[:5],   # newest first (leftmost), fetch 10 for duo detection
                            "avg_score": avg_score,
                            "recent_wr": recent_wr,
                            "champ_wr_map": champ_wr_map,
                            "main_champs": main_champs,
                            "streak": streak,
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
    for r in results:
        p_puuid = r["puuid"]
        for g in r.get("last5", []):
            match_participants = g.get("participants", [])
            match_id = g.get("matchId", "")
            if not match_id:
                continue
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
                for member in component:
                    duo_groups[member] = next_gid
                next_gid += 1
            
    # Inject duo info back into results
    for r in results:
        r["duo_group"] = duo_groups.get(r["puuid"], 0)

    return {r["puuid"]: r for r in results}

@router.post("/win-predict")
async def win_predict(body: WinPredictRequest):
    participants = [p.model_dump() for p in body.participants]
    return win_predictor.predict(participants, body.live_stats)

@router.get("/ingest/status")
async def ingest_status():
    return await db.get_ingestion_status()


@router.post("/ingest/toggle")
async def ingest_toggle():
    return await db.toggle_ingestion()


@router.post("/admin/retrain")
async def admin_retrain():
    result = await asyncio.to_thread(win_predictor.retrain_on_real_data)
    return result


@router.post("/ask")
async def ask_coach(body: AskRequest):
    system_prompt = f"You are a League of Legends coach. Be casual, direct, human. Bold stats. 2-3 sentences max.\n\nPlayer context:\n{body.context}"
    history = [{"role": m.role, "content": m.content} for m in body.history]
    answer = await ask_coach_question(system_prompt, history, body.question)
    return {"answer": answer}
