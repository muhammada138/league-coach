from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel
from typing import List
import asyncio
import httpx
import os
from collections import Counter
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_REGION = os.getenv("RIOT_REGION", "na1")
RIOT_ROUTING = os.getenv("RIOT_ROUTING", "americas")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

RIOT_HEADERS = {"X-Riot-Token": RIOT_API_KEY}

NUMERIC_STATS = [
    "kills", "deaths", "assists", "totalMinionsKilled",
    "visionScore", "totalDamageDealtToChampions", "goldEarned",
    "wardsPlaced", "wardsKilled",
]


def _compute_perf_score(player: dict, all_players: list) -> float:
    """
    0-100 performance score (reverse-engineered dpm.lol algorithm).
    Components: Base + Global + Lane + Objectives + Team + KDA + RoleSpecific + Win/Loss.
    Returns a float rounded to 2 decimal places.
    """
    ch   = player.get("challenges") or {}
    lane = player.get("teamPosition") or "MIDDLE"

    # ── BASE ─────────────────────────────────────────────────────────────────
    base = 15.0

    # ── GLOBAL ───────────────────────────────────────────────────────────────
    gpm  = ch.get("goldPerMinute")        or 0.0
    dpm  = ch.get("damagePerMinute")      or 0.0
    vspm = ch.get("visionScorePerMinute") or 0.0
    global_score = (gpm + 60) * 0.008 + (dpm - 24.6) * 0.007 + vspm * 2.0

    # ── KDA (role-dependent) ──────────────────────────────────────────────────
    kills   = player.get("kills",   0) or 0
    deaths  = player.get("deaths",  0) or 0
    assists = player.get("assists", 0) or 0
    if lane == "TOP":
        kda_score = kills * 0.80 + assists * 0.80 + deaths * -1.50
    elif lane == "UTILITY":
        kda_score = kills * 0.85 + assists * 0.90 + deaths * -1.25
    else:  # JUNGLE, MIDDLE, BOTTOM
        kda_score = kills * 0.75 + assists * 0.75 + deaths * -1.50

    # ── LANE PERFORMANCE (vs lane opponent) ───────────────────────────────────
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
            gold_diff  = (player.get("goldEarned", 0) or 0) - (opp.get("goldEarned", 0) or 0)
            xp_diff    = (player.get("champExperience", 0) or 0) - (opp.get("champExperience", 0) or 0)
            max_cs_adv = ch.get("maxCsAdvantageOnLaneOpponent", 0) or 0
            raw_lane   = gold_diff * 0.0015 + xp_diff * 0.0011 + max_cs_adv * 0.08
            lane_score = max(-5.0, min(10.0, raw_lane))

    # ── OBJECTIVES ────────────────────────────────────────────────────────────
    rift_heralds = ch.get("riftHeraldKills", 0)            or 0
    dragons      = player.get("dragonKills", 0)            or 0
    barons       = player.get("baronKills",  0)            or 0
    horde        = ch.get("voidMonsterKill", 0)            or 0
    obj_dmg      = player.get("damageDealtToObjectives", 0) or 0
    obj_score    = rift_heralds * 3.0 + dragons * 2.1 + barons * 2.0 + horde * 0.5 + obj_dmg * 0.00024

    # ── TEAM ──────────────────────────────────────────────────────────────────
    # Riot API challenges values are 0-1; convert to 0-100 for the formula
    kp_pct        = (ch.get("killParticipation",          0) or 0.0) * 100
    team_dmg_pct  = (ch.get("teamDamagePercentage",       0) or 0.0) * 100
    dmg_taken_pct = (ch.get("damageTakenOnTeamPercentage",0) or 0.0) * 100
    team_score    = (kp_pct - 25) * 0.14 + team_dmg_pct * 0.09 + dmg_taken_pct * 0.07

    # ── ROLE-SPECIFIC MASTERY ─────────────────────────────────────────────────
    lane_mins     = ch.get("laneMinionsFirst10Minutes", 0) or 0
    turret_plates = ch.get("turretPlatesTaken",         0) or 0
    solo_kills    = ch.get("soloKills",                 0) or 0

    if lane in ("TOP", "MIDDLE"):
        cs10_score = (lane_mins - 54.0) * 0.35
    elif lane == "BOTTOM":
        cs10_score = (lane_mins - 51.0) * 0.37
    else:
        cs10_score = 0.0

    plates_score = 2.25 + turret_plates * 1.50

    if lane == "BOTTOM":
        solo_score = solo_kills * 1.50
    elif lane == "MIDDLE":
        solo_score = solo_kills * 0.85
    elif lane == "TOP":
        solo_score = solo_kills * 0.75
    else:
        solo_score = 0.0

    role_specific = cs10_score + plates_score + solo_score

    # ── WIN / LOSS ────────────────────────────────────────────────────────────
    win_loss = 3.0 if player.get("win", False) else -3.0

    # ── TOTAL ────────────────────────────────────────────────────────────────
    total = base + global_score + lane_score + obj_score + team_score + kda_score + role_specific + win_loss
    return round(max(0.0, min(100.0, total)), 2)


def _compute_diffed_lane(all_players: list):
    """Return the position label where the two opposing players had the biggest score gap."""
    by_pos = {}
    for p in all_players:
        pos = p.get("teamPosition", "")
        if pos and pos != "UNKNOWN":
            by_pos.setdefault(pos, []).append(p)

    max_diff, diffed = -1, None
    for pos, players in by_pos.items():
        if len(players) != 2:
            continue
        s1 = _compute_perf_score(players[0], all_players)
        s2 = _compute_perf_score(players[1], all_players)
        diff = abs(s1 - s2)
        if diff > max_diff:
            max_diff, diffed = diff, pos
    return diffed


async def riot_get(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url, headers=RIOT_HEADERS)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.get("/summoner/{game_name}/{tag_line}")
async def get_summoner(game_name: str, tag_line: str):
    url = f"https://{RIOT_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        data = await riot_get(client, url)
    return {"puuid": data["puuid"], "gameName": data["gameName"], "tagLine": data["tagLine"]}


@app.get("/profile/{puuid}")
async def get_profile(puuid: str):
    async with httpx.AsyncClient() as client:
        summoner, entries = await asyncio.gather(
            riot_get(client, f"https://{RIOT_REGION}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"),
            riot_get(client, f"https://{RIOT_REGION}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"),
        )

    summoner_level = summoner.get("summonerLevel", 0)
    ranked = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)

    profile_icon_id = summoner.get("profileIconId", 0)

    if ranked is None:
        return {"summonerLevel": summoner_level, "profileIconId": profile_icon_id, "tier": "UNRANKED", "division": "", "lp": 0, "wins": 0, "losses": 0}

    return {
        "summonerLevel": summoner_level,
        "profileIconId": profile_icon_id,
        "tier": ranked["tier"],
        "division": ranked["rank"],
        "lp": ranked["leaguePoints"],
        "wins": ranked["wins"],
        "losses": ranked["losses"],
    }


@app.get("/analyze/{puuid}")
async def analyze(puuid: str, game_name: str = "Summoner"):
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch last 5 ranked match IDs
        match_ids = []
        queue_used = 420
        for try_queue in [420, 440, 400]:
            ids = await riot_get(
                client,
                f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=10&queue={try_queue}",
            )
            if ids:
                match_ids = ids
                queue_used = try_queue
                break

        if not match_ids:
            raise HTTPException(status_code=404, detail="No matches found")

        # 2. Fetch all match data in parallel
        match_datas = await asyncio.gather(*[
            riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}")
            for mid in match_ids
        ])

        games = []
        for match_id, match_data in zip(match_ids, match_datas):
            info = match_data["info"]
            participants = info["participants"]
            game_duration = info["gameDuration"]

            # 3. Find the player's participant entry
            player = next((p for p in participants if p["puuid"] == puuid), None)
            if player is None:
                continue

            # 4. Extract player stats
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

            # 5. Compute lobby averages across all 10 participants
            lobby_avgs = {}
            for stat in NUMERIC_STATS:
                lobby_avgs[stat] = sum(p[stat] for p in participants) / len(participants)

            # 6. Compute per-match deltas
            deltas = {stat: player_stats[stat] - lobby_avgs[stat] for stat in NUMERIC_STATS}

            # Derived per-game stats
            minutes = game_duration / 60
            player_cspm = player_stats["totalMinionsKilled"] / minutes if minutes > 0 else 0
            lobby_cspm = lobby_avgs["totalMinionsKilled"] / minutes if minutes > 0 else 0

            all_player_scores = [(p, _compute_perf_score(p, participants)) for p in participants]
            game_score = next(s for p, s in all_player_scores if p.get("puuid") == puuid)
            game_diffed_lane = _compute_diffed_lane(participants)
            winning_scores = [(p, s) for p, s in all_player_scores if p.get("win")]
            losing_scores  = [(p, s) for p, s in all_player_scores if not p.get("win")]
            mvp_puuid_g = max(winning_scores, key=lambda x: x[1])[0].get("puuid") if winning_scores else None
            ace_puuid_g = max(losing_scores,  key=lambda x: x[1])[0].get("puuid") if losing_scores  else None
            mvp_ace = "MVP" if puuid == mvp_puuid_g else ("ACE" if puuid == ace_puuid_g else None)

            player_team_id = player.get("teamId")
            teammates = [
                {
                    "gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
                    "puuid": p.get("puuid", ""),
                }
                for p in participants
                if p.get("puuid") != puuid and p.get("teamId") == player_team_id
            ]
            opponents = [
                {
                    "gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
                    "puuid": p.get("puuid", ""),
                }
                for p in participants
                if p.get("puuid") != puuid and p.get("teamId") != player_team_id
            ]

            games.append({
                "matchId": match_id,
                "playerStats": player_stats,
                "lobbyAverages": lobby_avgs,
                "deltas": deltas,
                "playerCspm": round(player_cspm, 2),
                "lobbyCspm": round(lobby_cspm, 2),
                "score": game_score,
                "diffedLane": game_diffed_lane,
                "mvpAce": mvp_ace,
                "teammates": teammates,
                "opponents": opponents,
            })

    if not games:
        raise HTTPException(status_code=404, detail="Could not process any matches")

    n = len(games)

    # 7. Aggregate across all games
    player_avgs = {}
    lobby_avgs_agg = {}
    for stat in NUMERIC_STATS:
        player_avgs[stat] = sum(g["playerStats"][stat] for g in games) / n
        lobby_avgs_agg[stat] = sum(g["lobbyAverages"][stat] for g in games) / n

    overall_deltas = {stat: player_avgs[stat] - lobby_avgs_agg[stat] for stat in NUMERIC_STATS}

    # CS per minute
    total_seconds = sum(g["playerStats"]["gameDuration"] for g in games)
    total_minutes = total_seconds / 60
    player_cspm = player_avgs["totalMinionsKilled"] / (total_minutes / n) if total_minutes > 0 else 0
    lobby_cspm = lobby_avgs_agg["totalMinionsKilled"] / (total_minutes / n) if total_minutes > 0 else 0

    # KDA
    player_kda = (player_avgs["kills"] + player_avgs["assists"]) / max(player_avgs["deaths"], 1)
    lobby_kda = (lobby_avgs_agg["kills"] + lobby_avgs_agg["assists"]) / max(lobby_avgs_agg["deaths"], 1)

    # Win rate
    wins = sum(1 for g in games if g["playerStats"]["win"])
    win_rate = round((wins / n) * 100, 1)

    # Most played position
    positions = [g["playerStats"]["teamPosition"] for g in games]
    most_common_position = Counter(positions).most_common(1)[0][0]

    # Per-game breakdown for prompt
    game_breakdown_lines = []
    for g in games:
        ps = g["playerStats"]
        kda_str = f"{ps['kills']}/{ps['deaths']}/{ps['assists']}"
        result = "WIN" if ps["win"] else "LOSS"
        game_breakdown_lines.append(
            f"  - {ps['championName']} ({ps['teamPosition']}): {kda_str}, "
            f"{g['playerCspm']} cspm, vision {ps['visionScore']}, {result}"
        )
    game_breakdown = "\n".join(game_breakdown_lines)

    def fmt(val: float) -> str:
        return f"{val:.2f}"

    def delta_str(val: float) -> str:
        return f"+{val:.2f}" if val >= 0 else f"{val:.2f}"

    # 8. Build Groq prompt and call API
    system_prompt = (
        "You are a League of Legends coach giving direct, personal feedback to this specific player. "
        "Always speak in second person: 'you', 'your', 'you're'. Talk like a real coach, not a report writer. "
        "Be blunt and human. No corporate filler like 'it appears', 'based on the data', or 'it seems'. "
        "Give 3-4 weaknesses where they are underperforming vs their lobby. "
        "Each tip: 1-2 sentences max. Lead with the problem, end with one concrete fix. "
        "Bold (**) every stat number and every key concept/stat name you mention so the player can scan quickly. "
        "GROUPING RULES, one tip max per group: "
        "(1) Vision = vision score + wards placed + wards killed. "
        "(2) Combat = KDA + kills + deaths + assists. "
        "(3) Economy = CS per minute + gold earned. "
        "Order by highest impact first. Format as a numbered list. No intro sentence, go straight to tip 1."
    )

    user_prompt = f"""Player: {game_name}
Most played role: {most_common_position}
Win rate last 10 games: {win_rate}%

Player averages vs lobby averages:
- KDA ratio: {fmt(player_kda)} vs {fmt(lobby_kda)} (delta: {delta_str(player_kda - lobby_kda)})
- CS per minute: {fmt(player_cspm)} vs {fmt(lobby_cspm)} (delta: {delta_str(player_cspm - lobby_cspm)})
- Vision score: {fmt(player_avgs['visionScore'])} vs {fmt(lobby_avgs_agg['visionScore'])} (delta: {delta_str(overall_deltas['visionScore'])})
- Damage dealt: {fmt(player_avgs['totalDamageDealtToChampions'])} vs {fmt(lobby_avgs_agg['totalDamageDealtToChampions'])} (delta: {delta_str(overall_deltas['totalDamageDealtToChampions'])})
- Gold earned: {fmt(player_avgs['goldEarned'])} vs {fmt(lobby_avgs_agg['goldEarned'])} (delta: {delta_str(overall_deltas['goldEarned'])})
- Wards placed: {fmt(player_avgs['wardsPlaced'])} vs {fmt(lobby_avgs_agg['wardsPlaced'])} (delta: {delta_str(overall_deltas['wardsPlaced'])})
- Wards killed: {fmt(player_avgs['wardsKilled'])} vs {fmt(lobby_avgs_agg['wardsKilled'])} (delta: {delta_str(overall_deltas['wardsKilled'])})

Per game breakdown:
{game_breakdown}"""

    groq_client = Groq(api_key=GROQ_API_KEY)
    completion = await asyncio.to_thread(
        groq_client.chat.completions.create,
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    coaching = completion.choices[0].message.content

    # 9. Return aggregated result
    game_summaries = []
    for g in games:
        ps = g["playerStats"]
        game_summaries.append({
            "matchId": g["matchId"],
            "championName": ps["championName"],
            "teamPosition": ps["teamPosition"],
            "kills": ps["kills"],
            "deaths": ps["deaths"],
            "assists": ps["assists"],
            "cspm": g["playerCspm"],
            "visionScore": ps["visionScore"],
            "win": ps["win"],
            "gameDuration": ps["gameDuration"],
            "score": g["score"],
            "diffedLane": g["diffedLane"],
            "mvpAce": g.get("mvpAce"),
            "teammates": g.get("teammates", []),
            "opponents": g.get("opponents", []),
        })

    diffed_lanes = [g["diffedLane"] for g in game_summaries if g["diffedLane"]]
    most_diffed_lane = Counter(diffed_lanes).most_common(1)[0][0] if diffed_lanes else None

    return {
        "gameName": game_name,
        "queueUsed": queue_used,
        "mostPlayedPosition": most_common_position,
        "winRate": win_rate,
        "mostDiffedLane": most_diffed_lane,
        "playerAverages": {stat: round(player_avgs[stat], 2) for stat in NUMERIC_STATS} | {
            "cspm": round(player_cspm, 2),
            "kda": round(player_kda, 2),
        },
        "lobbyAverages": {stat: round(lobby_avgs_agg[stat], 2) for stat in NUMERIC_STATS} | {
            "cspm": round(lobby_cspm, 2),
            "kda": round(lobby_kda, 2),
        },
        "deltas": {stat: round(overall_deltas[stat], 2) for stat in NUMERIC_STATS} | {
            "cspm": round(player_cspm - lobby_cspm, 2),
            "kda": round(player_kda - lobby_kda, 2),
        },
        "coaching": coaching,
        "games": game_summaries,
    }


@app.get("/history/{puuid}")
async def get_history(puuid: str, start: int = 0, count: int = 10, queue: int = 420):
    count = min(count, 10)
    async with httpx.AsyncClient(timeout=30.0) as client:
        match_ids = await riot_get(
            client,
            f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&queue={queue}",
        )
        if not match_ids:
            return []
        match_datas = await asyncio.gather(*[
            riot_get(client, f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{mid}")
            for mid in match_ids
        ])
    games = []
    for match_id, match_data in zip(match_ids, match_datas):
        info = match_data["info"]
        participants = info["participants"]
        player = next((p for p in participants if p["puuid"] == puuid), None)
        if player is None:
            continue
        minutes = info["gameDuration"] / 60
        cspm = round(player["totalMinionsKilled"] / minutes if minutes > 0 else 0, 2)
        player_team_id = player.get("teamId")
        hist_teammates = [
            {
                "gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
                "puuid": p.get("puuid", ""),
            }
            for p in participants
            if p.get("puuid") != puuid and p.get("teamId") == player_team_id
        ]
        hist_opponents = [
            {
                "gameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
                "puuid": p.get("puuid", ""),
            }
            for p in participants
            if p.get("puuid") != puuid and p.get("teamId") != player_team_id
        ]
        all_ps = [(p, _compute_perf_score(p, participants)) for p in participants]
        player_score_h = next(s for p, s in all_ps if p.get("puuid") == puuid)
        win_scores_h = [(p, s) for p, s in all_ps if p.get("win")]
        loss_scores_h = [(p, s) for p, s in all_ps if not p.get("win")]
        mvp_h = max(win_scores_h,  key=lambda x: x[1])[0].get("puuid") if win_scores_h  else None
        ace_h = max(loss_scores_h, key=lambda x: x[1])[0].get("puuid") if loss_scores_h else None
        mvp_ace_h = "MVP" if puuid == mvp_h else ("ACE" if puuid == ace_h else None)
        games.append({
            "matchId": match_id,
            "championName": player["championName"],
            "teamPosition": player.get("teamPosition", "UNKNOWN"),
            "kills": player["kills"],
            "deaths": player["deaths"],
            "assists": player["assists"],
            "cspm": cspm,
            "visionScore": player["visionScore"],
            "win": player["win"],
            "gameDuration": info["gameDuration"],
            "score": player_score_h,
            "mvpAce": mvp_ace_h,
            "diffedLane": _compute_diffed_lane(participants),
            "teammates": hist_teammates,
            "opponents": hist_opponents,
        })
    return games


@app.get("/match/{match_id}/scoreboard")
async def get_scoreboard(match_id: str):
    async with httpx.AsyncClient() as client:
        data = await riot_get(
            client,
            f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}",
        )
    participants = sorted(data["info"]["participants"], key=lambda p: p["teamId"])
    return [
        {
            "puuid": p.get("puuid", ""),
            "riotIdGameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
            "riotIdTagline": p.get("riotIdTagline") or "",
            "championName": p["championName"],
            "teamPosition": p.get("teamPosition", "UNKNOWN"),
            "kills": p["kills"],
            "deaths": p["deaths"],
            "assists": p["assists"],
            "totalMinionsKilled": p["totalMinionsKilled"],
            "visionScore": p["visionScore"],
            "totalDamageDealtToChampions": p["totalDamageDealtToChampions"],
            "goldEarned": p["goldEarned"],
            "champExperience": p.get("champExperience", 0),
            "dragonKills": p.get("dragonKills", 0),
            "baronKills": p.get("baronKills", 0),
            "damageDealtToObjectives": p.get("damageDealtToObjectives", 0),
            "win": p["win"],
            "teamId": p["teamId"],
            "challenges": {
                k: (p.get("challenges") or {}).get(k, 0)
                for k in (
                    "goldPerMinute", "damagePerMinute", "visionScorePerMinute",
                    "killParticipation", "teamDamagePercentage", "damageTakenOnTeamPercentage",
                    "laneMinionsFirst10Minutes", "turretPlatesTaken", "soloKills",
                    "maxCsAdvantageOnLaneOpponent", "riftHeraldKills", "voidMonsterKill",
                )
            },
        }
        for p in participants
    ]


@app.get("/live/{puuid}")
async def get_live_game(puuid: str):
    url = f"https://{RIOT_REGION}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=RIOT_HEADERS)
        if response.status_code == 404:
            return {"inGame": False}
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        data = response.json()

    participants = data.get("participants", [])
    return {
        "inGame": True,
        "gameId": data.get("gameId"),
        "gameMode": data.get("gameMode", ""),
        "queueId": data.get("gameQueueConfigId", 0),
        "gameLength": data.get("gameLength", 0),
        "participants": [
            {
                "puuid": p.get("puuid", ""),
                "summonerName": (p.get("riotId") or p.get("summonerName") or "Unknown").split("#")[0],
                "tagLine": ((p.get("riotId") or "#")).split("#")[-1],
                "championId": p.get("championId", 0),
                "teamId": p.get("teamId", 0),
            }
            for p in participants
        ],
    }


class ChatMessage(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    context: str
    history: List[ChatMessage] = []


@app.post("/ask")
async def ask_coach(body: AskRequest):
    groq_client = Groq(api_key=GROQ_API_KEY)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a League of Legends coach talking directly to this player. "
                "Always use second person: 'you', 'your'. Be casual, direct, and human. "
                "No filler phrases, no 'based on your data'. Bold (**) every number and key stat name you mention. "
                "Keep replies to 2-3 sentences max.\n\n"
                f"Player context:\n{body.context}"
            ),
        },
        *[{"role": m.role, "content": m.content} for m in body.history],
        {"role": "user", "content": body.question},
    ]
    completion = await asyncio.to_thread(
        groq_client.chat.completions.create,
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=300,
    )
    return {"answer": completion.choices[0].message.content}
