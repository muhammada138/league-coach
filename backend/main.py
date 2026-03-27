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
        match_ids = await riot_get(
            client,
            f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=20&queue=420",
        )

        if not match_ids:
            raise HTTPException(status_code=404, detail="No ranked matches found")

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

            games.append({
                "matchId": match_id,
                "playerStats": player_stats,
                "lobbyAverages": lobby_avgs,
                "deltas": deltas,
                "playerCspm": round(player_cspm, 2),
                "lobbyCspm": round(lobby_cspm, 2),
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

    # Per-game breakdown for prompt — cap at 10 most recent games
    ai_games = games[:10]
    game_breakdown_lines = []
    for g in ai_games:
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
        "Always speak in second person — 'you', 'your', 'you're'. Talk like a real coach, not a report writer. "
        "Be blunt and human. No corporate filler like 'it appears', 'based on the data', or 'it seems'. "
        "Give 3-4 weaknesses where they are underperforming vs their lobby. "
        "Each tip: 1-2 sentences max. Lead with the problem, end with one concrete fix. "
        "Bold (**) every stat number and every key concept/stat name you mention so the player can scan quickly. "
        "GROUPING RULES — one tip max per group: "
        "(1) Vision = vision score + wards placed + wards killed. "
        "(2) Combat = KDA + kills + deaths + assists. "
        "(3) Economy = CS per minute + gold earned. "
        "Order by highest impact first. Format as a numbered list. No intro sentence, go straight to tip 1."
    )

    user_prompt = f"""Player: {game_name}
Most played role: {most_common_position}
Win rate last 20 games: {win_rate}%

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
        })

    return {
        "gameName": game_name,
        "mostPlayedPosition": most_common_position,
        "winRate": win_rate,
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
            "riotIdGameName": p.get("riotIdGameName") or p.get("summonerName") or "Unknown",
            "championName": p["championName"],
            "kills": p["kills"],
            "deaths": p["deaths"],
            "assists": p["assists"],
            "totalMinionsKilled": p["totalMinionsKilled"],
            "visionScore": p["visionScore"],
            "totalDamageDealtToChampions": p["totalDamageDealtToChampions"],
            "goldEarned": p["goldEarned"],
            "win": p["win"],
            "teamId": p["teamId"],
        }
        for p in participants
    ]


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
                "Always use second person — 'you', 'your'. Be casual, direct, and human. "
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
