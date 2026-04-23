import httpx
import asyncio
import logging
from fastapi import HTTPException
from ..state import RIOT_HEADERS, rank_cache, timeline_cache, match_cache, RIOT_REGION, RIOT_ROUTING

# Configuration Constants
RETRY_DELAY_BUFFER_SEC = 1
MAX_RETRIES = 3
MIN_GAME_DURATION_SEC = 210
PERF_SCORE_BASE = 15.0

async def get_match_details(client: httpx.AsyncClient, match_id: str, routing: str = RIOT_ROUTING) -> dict:
    if match_id in match_cache:
        return match_cache[match_id]
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    try:
        data = await riot_get(client, url)
        match_cache[match_id] = data
        return data
    except Exception as e:
        logger.warning("Failed to fetch match details for %s: %s", match_id, e)
        raise e
from .rate_limiter import acquire as _rl_acquire, update_from_response as _rl_update

logger = logging.getLogger(__name__)

async def riot_get(client: httpx.AsyncClient, url: str) -> dict:
    for attempt in range(MAX_RETRIES):
        await _rl_acquire()
        response = await client.get(url, headers=RIOT_HEADERS)
        _rl_update(response)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            logger.warning("Riot API 429 despite limiter (attempt %d) — sleeping %ds", attempt + 1, retry_after)
            await asyncio.sleep(retry_after + RETRY_DELAY_BUFFER_SEC)
            continue
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()
    raise HTTPException(status_code=429, detail="Too many requests after multiple retries")

async def get_cached_rank(client: httpx.AsyncClient, puuid: str, region: str = RIOT_REGION):
    if not puuid:
        return "Unranked"
    if puuid in rank_cache:
        return rank_cache[puuid]
    try:
        entries = await riot_get(client, f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}")
        ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
        rank = f"{ranked['tier'].capitalize()} {ranked['rank']}" if ranked else "Unranked"
        rank_cache[puuid] = rank
        return rank
    except Exception as e:
        logger.warning("Failed to fetch rank for puuid %s in %s: %s", puuid, region, e)
        return "Unranked"

async def get_match_timeline(client: httpx.AsyncClient, match_id: str, routing: str = RIOT_ROUTING) -> dict:
    if match_id in timeline_cache:
        return timeline_cache[match_id]
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
    try:
        data = await riot_get(client, url)
        timeline_cache[match_id] = data
        return data
    except Exception as e:
        logger.warning("Failed to fetch timeline for match %s in %s: %s", match_id, routing, e)
    return None

def _compute_perf_score(player: dict, all_players: list, timeline: dict = None, game_duration: int = 0) -> float:
    if 0 < game_duration < MIN_GAME_DURATION_SEC:
        return 0.0

    ch   = player.get("challenges") or {}
    lane = player.get("teamPosition") or "MIDDLE"
    base = PERF_SCORE_BASE
    gpm  = ch.get("goldPerMinute", 0) or 0.0
    dpm  = ch.get("damagePerMinute", 0) or 0.0
    vspm = ch.get("visionScorePerMinute", 0) or 0.0
    global_score = (gpm + 60) * 0.008 + (dpm - 24.6) * 0.007 + vspm * 2.0

    kills   = player.get("kills",   0) or 0
    deaths  = player.get("deaths",  0) or 0
    assists = player.get("assists", 0) or 0
    if lane == "TOP":
        kda_score = kills * 0.80 + assists * 0.80 + deaths * -1.50
    elif lane == "UTILITY":
        kda_score = kills * 0.85 + assists * 0.90 + deaths * -1.25
    else:
        kda_score = kills * 0.75 + assists * 0.75 + deaths * -1.50

    player_team = player.get("teamId", 100)
    player_pos  = player.get("teamPosition") or ""
    lane_score  = 0.0
    if player_pos and player_pos not in ("", "UNKNOWN"):
        opp = next(
            (p for p in all_players
             if p.get("teamPosition") == player_pos and p.get("teamId") != player_team),
            None,
        )
        if opp:
            true_gold_diff = 0
            true_xp_diff = 0
            
            if timeline:
                frames = timeline.get("info", {}).get("frames", [])
                if frames:
                    target_frame_idx = min(15, len(frames) - 1)
                    p_frames = frames[target_frame_idx].get("participantFrames", {})
                    p_id = str(player.get("participantId"))
                    o_id = str(opp.get("participantId"))
                    p_frame = p_frames.get(p_id, {})
                    o_frame = p_frames.get(o_id, {})
                    true_gold_diff = p_frame.get("totalGold", 0) - o_frame.get("totalGold", 0)
                    true_xp_diff = p_frame.get("xp", 0) - o_frame.get("xp", 0)
            else:
                true_gold_diff = (player.get("goldEarned", 0) or 0) - (opp.get("goldEarned", 0) or 0)
                true_xp_diff = (player.get("champExperience", 0) or 0) - (opp.get("champExperience", 0) or 0)
                
            max_cs_adv = ch.get("maxCsAdvantageOnLaneOpponent", 0) or 0
            raw_lane   = (true_gold_diff * 0.0015) + (true_xp_diff * 0.0011) + (max_cs_adv * 0.08)
            lane_score = max(-5.0, min(10.0, raw_lane))

    rift_heralds = ch.get("riftHeraldKills", 0)            or 0
    dragons      = player.get("dragonKills", 0)            or 0
    barons       = player.get("baronKills",  0)            or 0
    horde        = ch.get("voidMonsterKill", 0)            or 0
    obj_dmg      = player.get("damageDealtToObjectives", 0) or 0
    obj_score    = rift_heralds * 3.0 + dragons * 2.1 + barons * 2.0 + horde * 0.5 + obj_dmg * 0.00024

    kp_pct        = (ch.get("killParticipation",          0) or 0.0) * 100
    team_dmg_pct  = (ch.get("teamDamagePercentage",       0) or 0.0) * 100
    dmg_taken_pct = (ch.get("damageTakenOnTeamPercentage",0) or 0.0) * 100
    team_score    = (kp_pct - 25) * 0.14 + team_dmg_pct * 0.09 + dmg_taken_pct * 0.07

    role_specific = 0.0
    if lane in ("TOP", "MIDDLE", "BOTTOM"):
        lane_mins     = ch.get("laneMinionsFirst10Minutes", 0) or 0
        turret_plates = ch.get("turretPlatesTaken",         0) or 0
        solo_kills    = ch.get("soloKills",                 0) or 0
        turret_tds    = ch.get("turretTakedowns",           0) or 0
        cs10_score = 0.0
        if lane_mins > 0 and lane in ("TOP", "MIDDLE"):
            cs10_score = (lane_mins - 54.0) * 0.35
        elif lane_mins > 0:
            cs10_score = (lane_mins - 51.0) * 0.35
        plates_score = 2.25 + turret_plates * 1.50
        if lane == "BOTTOM":
            solo_score = solo_kills * 1.50
        elif lane == "MIDDLE":
            solo_score = solo_kills * 0.85
        else:
            solo_score = solo_kills * 0.75
        td_score = turret_tds * 0.85 if lane == "TOP" else turret_tds * 0.75
        role_specific = cs10_score + plates_score + solo_score + td_score
    elif lane == "JUNGLE":
        init_crab    = ch.get("initialCrabCount",        0) or 0
        scuttle_crab = ch.get("scuttleCrabKills",        0) or 0
        jungle_cs10  = ch.get("jungleCsBefore10Minutes", 0) or 0
        enemy_jg     = ch.get("enemyJungleMonsterKills", 0) or 0
        pick_kill    = ch.get("pickKillWithAlly",        0) or 0
        role_specific = (init_crab * 1.50 + scuttle_crab * 0.45 + jungle_cs10 * 0.067 + enemy_jg * 0.50 + pick_kill * 0.275)
    else:
        support_quest = ch.get("completeSupportQuestInTime", 0) or 0
        stealth_wards = ch.get("stealthWardsPlaced",         0) or 0
        control_wards = ch.get("controlWardsPlaced",         0) or 0
        ward_tds      = ch.get("wardTakedowns",              0) or 0
        pick_kill     = ch.get("pickKillWithAlly",           0) or 0
        quest_score = 1.50 if support_quest else -3.0
        role_specific = (quest_score + stealth_wards * 0.17 + control_wards * 0.58 + ward_tds * 0.42 + pick_kill * 0.22)
    role_specific = max(0.0, min(20.0, role_specific))

    win_loss = 3.0 if player.get("win", False) else -3.0
    total = base + global_score + lane_score + obj_score + team_score + kda_score + role_specific + win_loss
    return round(max(0.0, min(100.0, float(total))), 2)

def _compute_diffed_lane(all_players: list, timeline: dict = None, game_duration: int = 0):
    by_pos = {}
    for p in all_players:
        pos = p.get("teamPosition", "")
        if pos and pos != "UNKNOWN":
            by_pos.setdefault(pos, []).append(p)
    max_diff, diffed = -1, None
    for pos, players in by_pos.items():
        if len(players) != 2: continue
        s1 = _compute_perf_score(players[0], all_players, timeline, game_duration)
        s2 = _compute_perf_score(players[1], all_players, timeline, game_duration)
        diff = abs(s1 - s2)
        if diff > max_diff:
            max_diff, diffed = diff, pos
    return diffed
