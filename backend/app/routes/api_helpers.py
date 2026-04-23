from typing import List, Dict, Any, Tuple
from collections import Counter
from fastapi import HTTPException
import httpx
import asyncio
from ..state import match_ids_cache
from ..services.riot import riot_get, _compute_perf_score, _compute_diffed_lane
from ..services.groq import get_coaching_feedback

NUMERIC_STATS = [
    "kills", "deaths", "assists", "totalMinionsKilled",
    "visionScore", "totalDamageDealtToChampions", "goldEarned",
    "wardsPlaced", "wardsKilled",
]

async def _fetch_recent_matches(client: httpx.AsyncClient, puuid: str, routing: str, count: int) -> Tuple[List[str], int, List[Any]]:
    cache_key = f"{puuid}_{count}"
    if cache_key in match_ids_cache:
        cached_ids, cached_q = match_ids_cache[cache_key]
        # We still need match_datas, but get_match_details in api.py handles its own cache
        return cached_ids, cached_q, []

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
            
    # Fallback: if no matches in prioritized queues, fetch ANY match
    if not match_ids:
        try:
            fallback_ids = await riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}")
            if isinstance(fallback_ids, list) and fallback_ids:
                match_ids = fallback_ids
                queue_used = 0 # 0 denotes mixed/unknown queue
        except Exception:
            pass

    if not match_ids: raise HTTPException(status_code=404, detail="No matches found")
    
    # Cache the result
    match_ids_cache[cache_key] = (match_ids, queue_used)

    match_tasks = [riot_get(client, f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{mid}") for mid in match_ids]
    match_datas = await asyncio.gather(*match_tasks, return_exceptions=True)
    return match_ids, queue_used, match_datas

def _process_match(match_id: str, match_data: dict, puuid: str) -> Dict[str, Any]:
    info = match_data["info"]
    participants = info["participants"]
    for p in participants:
        p["totalMinionsKilled"] = p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0)
    game_duration = info["gameDuration"]
    game_end_timestamp = info.get("gameEndTimestamp") or (info.get("gameCreation", 0) + game_duration * 1000)
    player = next((p for p in participants if p["puuid"] == puuid), None)
    if player is None: return None
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
    
    # Role-aware Vision Comparison: Don't compare carries to supports
    is_support = player.get("teamPosition") == "UTILITY"
    vis_group = [p for p in participants if (p.get("teamPosition") == "UTILITY") == is_support]
    if vis_group:
        role_vis_avg = sum(p["visionScore"] for p in vis_group) / len(vis_group)
        lobby_avgs["visionScore"] = role_vis_avg

    deltas = {stat: player_stats[stat] - lobby_avgs[stat] for stat in NUMERIC_STATS}
    minutes = game_duration / 60
    player_cspm = player_stats["totalMinionsKilled"] / minutes if minutes > 0 else 0
    lobby_cspm = lobby_avgs["totalMinionsKilled"] / minutes if minutes > 0 else 0
    all_player_scores = [(p, _compute_perf_score(p, participants, None, game_duration)) for p in participants]
    game_score = next(s for p, s in all_player_scores if p.get("puuid") == puuid)
    game_diffed_lane = _compute_diffed_lane(participants, all_player_scores, None, game_duration)
    winning_scores = [(p, s) for p, s in all_player_scores if p.get("win")]
    losing_scores  = [(p, s) for p, s in all_player_scores if not p.get("win")]
    mvp_puuid_g = max(winning_scores, key=lambda x: x[1])[0].get("puuid") if winning_scores else None
    ace_puuid_g = max(losing_scores,  key=lambda x: x[1])[0].get("puuid") if losing_scores  else None
    mvp_ace = "MVP" if puuid == mvp_puuid_g else ("ACE" if puuid == ace_puuid_g else None)
    player_team_id = player.get("teamId")
    teammates = [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "tagLine": p.get("riotIdTagline", ""), "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") == player_team_id]
    opponents = [{"gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown", "tagLine": p.get("riotIdTagline", ""), "puuid": p.get("puuid", "")} for p in participants if p.get("puuid") != puuid and p.get("teamId") != player_team_id]

    return {
        "matchId": match_id, "gameEndTimestamp": game_end_timestamp, "playerStats": player_stats, "lobbyAverages": lobby_avgs,
        "deltas": deltas, "playerCspm": round(player_cspm, 2), "lobbyCspm": round(lobby_cspm, 2), "score": game_score,
        "diffedLane": game_diffed_lane, "mvpAce": mvp_ace, "teammates": teammates, "opponents": opponents,
    }

def _aggregate_games_stats(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(games)
    player_avgs = {stat: sum(g["playerStats"][stat] for g in games) / n for stat in NUMERIC_STATS}
    lobby_avgs_agg = {stat: sum(g["lobbyAverages"][stat] for g in games) / n for stat in NUMERIC_STATS}
    total_seconds = sum(g["playerStats"]["gameDuration"] for g in games)
    total_minutes = total_seconds / 60
    player_cspm = player_avgs["totalMinionsKilled"] / (total_minutes / n) if total_minutes > 0 else 0
    lobby_cspm = lobby_avgs_agg["totalMinionsKilled"] / (total_minutes / n) if total_minutes > 0 else 0
    player_kda = (player_avgs["kills"] + player_avgs["assists"]) / max(player_avgs["deaths"], 1)
    lobby_kda = (lobby_avgs_agg["kills"] + lobby_avgs_agg["assists"]) / max(lobby_avgs_agg["deaths"], 1)
    wins = sum(1 for g in games if g["playerStats"]["win"])
    win_rate = round((wins / n) * 100, 1)
    positions = [g["playerStats"]["teamPosition"] for g in games if g["playerStats"]["teamPosition"] not in (None, "", "UNKNOWN")]
    most_common_position = Counter(positions).most_common(1)[0][0] if positions else "UNKNOWN"
    champ_names = [g["playerStats"]["championName"] for g in games]
    most_played_champ = Counter(champ_names).most_common(1)[0][0]
    champ_counter = Counter(champ_names)
    champ_wins = Counter(g["playerStats"]["championName"] for g in games if g["playerStats"]["win"])
    champ_breakdown = ", ".join(
        f"{champ} ({champ_wins.get(champ, 0)}W/{count - champ_wins.get(champ, 0)}L)"
        for champ, count in champ_counter.most_common()
    )

    champ_stats: dict[str, dict] = {}
    for g in games:
        ps = g["playerStats"]
        name = ps["championName"]
        if name not in champ_stats:
            champ_stats[name] = {"wins": 0, "games": 0, "kills": 0, "deaths": 0, "assists": 0}
        champ_stats[name]["games"] += 1
        if ps["win"]: champ_stats[name]["wins"] += 1
        champ_stats[name]["kills"] += ps["kills"]
        champ_stats[name]["deaths"] += ps["deaths"]
        champ_stats[name]["assists"] += ps["assists"]

    return {
        "n": n,
        "player_avgs": player_avgs,
        "lobby_avgs_agg": lobby_avgs_agg,
        "player_cspm": player_cspm,
        "lobby_cspm": lobby_cspm,
        "player_kda": player_kda,
        "lobby_kda": lobby_kda,
        "win_rate": win_rate,
        "most_common_position": most_common_position,
        "most_played_champ": most_played_champ,
        "champ_breakdown": champ_breakdown,
        "champ_stats": champ_stats,
    }

async def _generate_coaching(game_name: str, stats: Dict[str, Any], games: List[Dict[str, Any]] = None) -> str:
    game_history_context = ""
    if games:
        game_history_context = "RECENT MATCH HISTORY (Newest First):\n"
        for i, g in enumerate(games[:10]):
            ps = g["playerStats"]
            res = "W" if ps["win"] else "L"
            mvp = f" [{g['mvpAce']}]" if g.get("mvpAce") else ""
            game_history_context += f"- Match {i+1}: {res}, {ps['championName']}, {ps['kills']}/{ps['deaths']}/{ps['assists']}, Score: {g['score']}{mvp}\n"
    
    system_prompt = (
        "You are an Elite League of Legends Macro Analyst. Give lethal, high-Elo strategic feedback. "
        "Speak in second person: 'you', 'your'. Speak like a professional coach, not a data reporter. "
        "STRICT RULE: NO GENERIC ADVICE. Never tell them to 'buy items', 'ward more', or 'keep up the good work'. "
        "Every tip must focus on MACRO concepts: Tempo, Pathing efficiency, Objective setup, Wave state, or Item Spikes.\n\n"
        "EVALUATION HIERARCHY:\n"
        "1. STREAK MODE: If you see multiple [MVP] or high scores, PRIORITIZE dominance. IGNORE Vision/Wards entirely — they are carrying anyway. Focus on 'How to finish the game faster'.\n"
        "2. CORE STATS ONLY: Focus on Kills, CS, Gold, and Objective damage. Vision score is mathematically biased by Supports — only mention it if they are LOSING and getting caught constantly.\n\n"
        "THE 'GOLD STANDARD' TIP (Example of what to write):\n"
        "'In your Match 3 loss on Ornn (0/7/1), you struggled to make an impact. Focus on surviving the early levels and soaking XP until you hit level 6, avoiding aggressive trades.'\n\n"
        "FEEDBACK RULES:\n"
        "- Each tip: 1-2 sentences. Lead with a strategic insight, end with a concrete macro fix.\n"
        "- Bold (**) every stat number and every key concept/mechanic.\n"
        "- CRITICAL: If you reference a specific match from their history, YOU MUST ONLY give advice for the Champion they played IN THAT SPECIFIC MATCH. Never mention their 'Main Champion's' abilities when analyzing a game where they played a completely different champion.\n"
        "- CRITICAL: Reference abilities accurately for the champion in question (e.g. Ornn's W, Malphite's Q) and keep it contextually tied to the match.\n"
        "FORMATTING: 3-4 numbered tips. No intro/outro text."
    )
    user_prompt = (
        f"Player: {game_name}\n"
        f"Role: {stats['most_common_position']}\n"
        f"Win Rate: {stats['win_rate']}%\n\n"
        f"CHAMPION POOL (Overall Performance):\n"
        f"{stats['champ_breakdown']}\n\n"
        f"{game_history_context}\n"
        f"PLAYER AVERAGES (VS LOBBY AVERAGES):\n"
        f"- KDA: {stats['player_kda']:.2f} (Lobby: {stats['lobby_kda']:.2f})\n"
        f"- CSPM: {stats['player_cspm']:.2f} (Lobby: {stats['lobby_cspm']:.2f})\n"
        f"- Vision: {stats['player_avgs']['visionScore']:.1f} (Role-Adjusted Avg: {stats['lobby_avgs_agg']['visionScore']:.1f})\n"
        f"- Dmg/Gold: {stats['player_avgs']['totalDamageDealtToChampions']:.0f} / {stats['player_avgs']['goldEarned']:.0f}"
    )
    return await get_coaching_feedback(system_prompt, user_prompt)

def _build_game_summaries(games: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], str]:
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
    return game_summaries, most_diffed_lane
