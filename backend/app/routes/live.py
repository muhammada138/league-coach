import asyncio
import itertools

import httpx
from fastapi import APIRouter, HTTPException

from ..services import db
from ..services.riot import riot_get, get_cached_rank, get_match_details, _compute_perf_score
from ..state import (
    RIOT_REGION, get_routing, enriched_cache, MATCH_FETCH_SEM
)
from ..models.requests import LiveEnrichRequest

router = APIRouter(tags=["Live Game"])

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
    _RANKED_RANK_TYPE = {420: "RANKED_SOLO_5x5", 440: "RANKED_FLEX_SR"}
    rank_type = _RANKED_RANK_TYPE.get(body.queue_id, "RANKED_SOLO_5x5")
    is_ranked_queue = body.queue_id in _RANKED_RANK_TYPE
    match_queue_filter = body.queue_id

    async def enrich_one(puuid: str):
        region = getattr(body, 'region', RIOT_REGION)
        routing = get_routing(region)
        
        if not body.force:
            db_cached = db.get_enriched_profile(puuid)
            if db_cached:
                data, ts = db_cached
                data["puuid"] = puuid
                data["last_updated"] = ts
                return data

        cache_key = f"v7:{puuid}:{body.queue_id}:{region}"
        if not body.force:
            cached = enriched_cache.get(cache_key)
            if cached:
                return cached

        base = {
            "puuid": puuid, "tier": "UNRANKED", "division": "", "lp": 0,
            "wins": 0, "losses": 0, "last5": [], "avg_score": 50,
            "recent_wr": 0.5, "champ_wr_map": {}, "main_champs": [], "streak": 0,
        }
        api_failed = False
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                from ..state import summoner_cache
                cached_sum = summoner_cache.get(puuid)
                
                tasks = [
                    riot_get(client, f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
                    riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=5&queue={match_queue_filter}"),
                    riot_get(client, f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count=20"),
                ]
                
                if not cached_sum:
                    tasks.append(riot_get(client, f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"))
                
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                entries = task_results[0]
                match_ids = task_results[1]
                mastery_data = task_results[2]
                
                if cached_sum:
                    summoner_level, profile_icon_id = cached_sum
                    summoner_data = {"summonerLevel": summoner_level, "profileIconId": profile_icon_id}
                else:
                    summoner_data = task_results[3]
                    if not isinstance(summoner_data, Exception):
                        summoner_level = summoner_data.get("summonerLevel", 0)
                        profile_icon_id = summoner_data.get("profileIconId", 0)
                        summoner_cache.set(puuid, (summoner_level, profile_icon_id))

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
                                streak += direction
                            else:
                                break
                        from collections import Counter as _Counter
                        main_champs = [cid for cid, _ in _Counter(champ_ids).most_common(3)]
                        positions = [g.get("position", "UNKNOWN") for g in recent_results if g.get("position") != "UNKNOWN"]
                        most_common_pos = _Counter(positions).most_common(1)[0][0] if positions else "UNKNOWN"
                        
                        ui_last5 = [{"win": g["win"], "score": g["score"], "matchId": g["matchId"]} for g in recent_results[:5]]
                        
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
                            "last5_details": recent_results[:5],
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
            db.save_enriched_profile(puuid, base)
        return base

    results = await asyncio.gather(*[enrich_one(p) for p in body.puuids[:10]])
    
    live_puuids = {r["puuid"] for r in results if r.get("puuid")}
    
    pair_match_sets = {}  
    match_outcomes = {}   
    for r in results:
        if not r or not isinstance(r, dict):
            continue
        p_puuid = r.get("puuid")
        if not p_puuid:
            continue
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

    adj = {p: set() for p in live_puuids}
    for pair, match_ids in pair_match_sets.items():
        if len(match_ids) >= 2:
            p1, p2 = pair
            adj[p1].add(p2)
            adj[p2].add(p1)
            
    duo_groups = {}
    next_gid = 1
    visited = set()
    for p in live_puuids:
        if p not in visited and adj[p]:
            q = [p]
            component = []
            while q:
                curr = q.pop(0)
                if curr not in visited:
                    visited.add(curr)
                    component.append(curr)
                    q.extend(list(adj[curr]))
            
            if len(component) > 1:
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
            
    final_results = {}
    for i, puuid in enumerate(body.puuids[:10]):
        # Prefer the enriched result if it exists and has the right PUUID
        res = results[i] if i < len(results) else None
        if res and isinstance(res, dict) and res.get("puuid") == puuid:
            r = res
        else:
            # Fallback for failed/skipped enrichment
            r = {
                "puuid": puuid, "tier": "UNRANKED", "division": "", "lp": 0,
                "wins": 0, "losses": 0, "last5": [], "avg_score": 50,
                "recent_wr": 0.5, "champ_wr_map": {}, "main_champs": [], "streak": 0
            }
        
        # Add duo info if present
        info = duo_groups.get(puuid)
        if info:
            r["duo_group"] = info["gid"]
            r["duo_wr"] = info["wr"]
            r["duo_label"] = info["label"]
        else:
            r["duo_group"] = 0
            
        final_results[puuid] = r

    return final_results
