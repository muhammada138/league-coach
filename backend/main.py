from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
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
RIOT_ROUTING = os.getenv("RIOT_ROUTING", "americas")

RIOT_HEADERS = {"X-Riot-Token": RIOT_API_KEY}


@app.get("/summoner/{game_name}/{tag_line}")
async def get_summoner(game_name: str, tag_line: str):
    url = f"https://{RIOT_ROUTING}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=RIOT_HEADERS)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json()
    return {"puuid": data["puuid"], "gameName": data["gameName"], "tagLine": data["tagLine"]}


@app.get("/matches/{puuid}")
async def get_matches(puuid: str):
    url = f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=5&queue=420"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=RIOT_HEADERS)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.get("/match/{match_id}")
async def get_match(match_id: str, puuid: str = Query(...)):
    url = f"https://{RIOT_ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=RIOT_HEADERS)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json()
    info = data["info"]
    participant = next((p for p in info["participants"] if p["puuid"] == puuid), None)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found in match")
    return {
        "championName": participant["championName"],
        "teamPosition": participant["teamPosition"],
        "kills": participant["kills"],
        "deaths": participant["deaths"],
        "assists": participant["assists"],
        "totalMinionsKilled": participant["totalMinionsKilled"],
        "visionScore": participant["visionScore"],
        "totalDamageDealtToChampions": participant["totalDamageDealtToChampions"],
        "gameDuration": info["gameDuration"],
        "win": participant["win"],
    }
