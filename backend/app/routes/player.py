import asyncio
import time
import httpx
from fastapi import APIRouter, HTTPException

from ..services import db
from ..services.riot import riot_get, _compute_perf_score, _compute_diffed_lane
from ..state import (
    RIOT_REGION, RIOT_ROUTING, route_cache, 
    CACHE_VERSION, get_routing
)

router = APIRouter(tags=["Player"])

async def backfill_if_needed(puuid: str, tier: str, division: str, lp: int, wins: int, losses: int):
    if await db.has_history(puuid):
        return
    
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
            
            for match_data in match_datas:
                if isinstance(match_data, Exception): continue
                info = match_data["info"]
                p = next((p for p in info["participants"] if p["puuid"] == puuid), None)
                if not p: continue
                
                ts = int((info.get("gameEndTimestamp") or (info.get("gameCreation", 0) + info["gameDuration"] * 1000)) / 1000)
                snapshots.append((puuid, tier, division, curr_lp, curr_wins, curr_losses, ts, 'RANKED_SOLO_5x5'))
                
                if p["win"]:
                    curr_lp -= 20
                    curr_wins -= 1
                else:
                    curr_lp += 17
                    curr_losses -= 1
                
                if curr_lp < 0: curr_lp = 0
                if curr_lp > 100: curr_lp = 100
            
            await db.record_many_lp_snapshots(snapshots)
        except Exception as e:
            print(f"Backfill failed: {e}")

@router.get("/summoner/{game_name}/{tag_line}")
async def get_summoner(game_name: str, tag_line: str, region: str = RIOT_REGION):
    from ..state import account_cache
    cache_key = f"account:{region}:{game_name.lower()}:{tag_line.lower()}"
    cached = account_cache.get(cache_key)
    if cached:
        return cached

    routing = get_routing(region)
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        data = await riot_get(client, url)
    res = {"puuid": data["puuid"], "gameName": data["gameName"], "tagLine": data["tagLine"]}
    account_cache.set(cache_key, res)
    return res

@router.get("/profile/{puuid}")
async def get_profile(puuid: str, region: str = RIOT_REGION, force: bool = False):
    if not force:
        cached = db.get_enriched_profile(puuid)
        if cached:
            data, ts = cached
            if data.get("profileIconId"):
                data["last_updated"] = ts
                return data

    async with httpx.AsyncClient() as client:
        summoner, entries = await asyncio.gather(
            riot_get(client, f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"),
            riot_get(client, f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
        )
        summoner_level = summoner.get("summonerLevel", 0)
        profile_icon_id = summoner.get("profileIconId", 0)
    
    ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
    if not ranked:
        ranked = next((e for e in entries if "RANKED" in e.get("queueType", "")), None)
        
    flex = next((e for e in entries if e.get("queueType") == "RANKED_FLEX_SR"), None)
    
    def entry_data(e):
        if e is None:
            return {"tier": "UNRANKED", "division": "", "lp": 0, "wins": 0, "losses": 0}
        return {"tier": e["tier"], "division": e["rank"], "lp": e["leaguePoints"], "wins": e["wins"], "losses": e["losses"]}
    
    ranked_data = entry_data(ranked)
    flex_data   = entry_data(flex)

    res = {
        "summonerLevel": summoner_level,
        "profileIconId": profile_icon_id,
        **ranked_data,
        "flex": flex_data,
    }
    
    db.save_enriched_profile(puuid, res)
    res["last_updated"] = int(time.time())

    asyncio.create_task(db.record_lp_snapshot(puuid, ranked_data["tier"], ranked_data["division"], ranked_data["lp"], ranked_data["wins"], ranked_data["losses"], queue='RANKED_SOLO_5x5'))
    asyncio.create_task(db.record_lp_snapshot(puuid, flex_data["tier"], flex_data["division"], flex_data["lp"], flex_data["wins"], flex_data["losses"], queue='RANKED_FLEX_SR'))
    asyncio.create_task(backfill_if_needed(puuid, ranked_data["tier"], ranked_data["division"], ranked_data["lp"], ranked_data["wins"], ranked_data["losses"]))
    
    return res

@router.get("/lp-history/{puuid}")
async def lp_history(puuid: str, queue: str = 'RANKED_SOLO_5x5'):
    return await db.get_lp_history(puuid, queue=queue, days=30)

@router.get("/history/{puuid}")
async def get_history(puuid: str, start: int = 0, count: int = 10, queue: int = 420, region: str = RIOT_REGION):
    count = min(count, 10)
    routing = get_routing(region)
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
