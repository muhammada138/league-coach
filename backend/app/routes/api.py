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
from ..state import RIOT_REGION, RIOT_ROUTING, route_cache
from ..models.requests import LiveEnrichRequest, AskRequest

router = APIRouter()

NUMERIC_STATS = [
    "kills", "deaths", "assists", "totalMinionsKilled",
    "visionScore", "totalDamageDealtToChampions", "goldEarned",
    "wardsPlaced", "wardsKilled",
]

@router.get("/summoner/{game_name}/{tag_line}")
async def get_summoner(game_name: str, tag_line: str):
    url = f"https://{RIOT_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        data = await riot_get(client, url)
    return {"puuid": data["puuid"], "gameName": data["gameName"], "tagLine": data["tagLine"]}

@router.get("/profile/{puuid}")
async def get_profile(puuid: str):
    async with httpx.AsyncClient() as client:
        summoner, entries = await asyncio.gather(
            riot_get(client, f"https://{RIOT_REGION}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"),
            riot_get(client, f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
        )
    summoner_level = summoner.get("summonerLevel", 0)
    ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
    flex   = next((e for e in entries if e.get("queueType") == "RANKED_FLEX_SR"),   None)
    profile_icon_id = summoner.get("profileIconId", 0)
    def entry_data(e):
        if e is None:
            return {"tier": "UNRANKED", "division": "", "lp": 0, "wins": 0, "losses": 0}
        return {"tier": e["tier"], "division": e["rank"], "lp": e["leaguePoints"], "wins": e["wins"], "losses": e["losses"]}
    return {
        "summonerLevel": summoner_level,
        "profileIconId": profile_icon_id,
        **entry_data(ranked),
        "flex": entry_data(flex),
    }

@router.get("/analyze/{puuid}")
async def analyze(puuid: str, game_name: str = "Summoner"):
    cache_key = f"analyze:{puuid}"
    cached = route_cache.get(cache_key)
    if cached is not None: return cached
    async with httpx.AsyncClient(timeout=30.0) as client:
        queue_priorities = [420, 440, 400]
        id_tasks = [
            riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=5&queue={q}")
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
        match_tasks = [riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}") for mid in match_ids]
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
            teammates = [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") == player_team_id]
            opponents = [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") != player_team_id]
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
    
    # Groq Logic
    system_prompt = (
        "You are a League of Legends coach giving direct, personal feedback to this specific player. "
        "Always speak in second person: 'you', 'your', 'you're'. Talk like a real coach, not a report writer. "
        "Be blunt and human. No corporate filler. Give 3-4 weaknesses where they are underperforming vs their lobby. "
        "Each tip: 1-2 sentences max. Lead with the problem, end with one concrete fix. "
        "Bold (**) every stat number and every key concept/stat name. "
        "GROUPING RULES: (1) Vision (2) Combat (3) Economy. No intro sentence."
    )
    user_prompt = f"Player: {game_name}\nMost played role: {most_common_position}\nWin rate last 5 games: {win_rate}%\n\nPlayer averages vs lobby averages:\n- KDA: {player_kda:.2f} vs {lobby_kda:.2f}\n- CSPM: {player_cspm:.2f} vs {lobby_cspm:.2f}\n- Vision: {player_avgs['visionScore']:.2f} vs {lobby_avgs_agg['visionScore']:.2f}\n..."
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
async def get_history(puuid: str, start: int = 0, count: int = 10, queue: int = 420):
    count = min(count, 10)
    cache_key = f"history:{puuid}:{start}:{count}:{queue}"
    cached = route_cache.get(cache_key)
    if cached is not None: return cached
    async with httpx.AsyncClient(timeout=30.0) as client:
        match_ids = await riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&queue={queue}")
        if not match_ids: return []
        match_tasks = [riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}") for mid in match_ids]
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
            "teammates": [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") == player_team_id],
            "opponents": [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") != player_team_id],
        })
    route_cache.set(cache_key, games)
    return games

@router.get("/match/{match_id}/scoreboard")
async def get_scoreboard(match_id: str):
    async with httpx.AsyncClient() as client:
        data = await riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}")
    participants = sorted(data["info"]["participants"], key=lambda p: p["teamId"])
    for p in participants: p["totalMinionsKilled"] = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
    async with httpx.AsyncClient() as c2:
        ranks = await asyncio.gather(*[get_cached_rank(c2, p.get("puuid", "")) for p in participants], return_exceptions=True)
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
async def get_live_game(puuid: str):
    url = f"https://{RIOT_REGION}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    async with httpx.AsyncClient() as client:
        try:
            data = await riot_get(client, url)
            return {
                "inGame": True, "gameId": data.get("gameId"), "gameMode": data.get("gameMode", ""),
                "participants": [{"puuid": p.get("puuid", ""), "summonerName": (p.get("riotId") or p.get("summonerName") or "Unknown").split("#")[0], "tagLine": (p.get("riotId") or "").split("#")[1] if "#" in (p.get("riotId") or "") else "", "teamId": p.get("teamId", 0), "championId": p.get("championId", 0)} for p in data.get("participants", [])],
            }
        except HTTPException as e:
            if e.status_code == 404: return {"inGame": False}
            raise e

@router.post("/live-enrich")
async def live_enrich(body: LiveEnrichRequest):
    async def enrich_one(puuid: str):
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                entries = await riot_get(client, f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}")
                ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
                return {"puuid": puuid, "tier": ranked["tier"] if ranked else "UNRANKED", "lp": ranked.get("leaguePoints", 0) if ranked else 0}
        except: return {"puuid": puuid, "tier": "UNRANKED", "lp": 0}
    results = await asyncio.gather(*[enrich_one(p) for p in body.puuids[:10]])
    return {r["puuid"]: r for r in results}

@router.post("/ask")
async def ask_coach(body: AskRequest):
    system_prompt = f"You are a League of Legends coach. Be casual, direct, human. Bold stats. 2-3 sentences max.\n\nPlayer context:\n{body.context}"
    history = [{"role": m.role, "content": m.content} for m in body.history]
    answer = await ask_coach_question(system_prompt, history, body.question)
    return {"answer": answer}
