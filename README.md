# League Coach

AI-powered League of Legends coaching tool using Riot API and Groq.

## Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
uvicorn main:app --reload
```

## Endpoints

- `GET /summoner/{game_name}/{tag_line}` — Look up a player by Riot ID
- `GET /matches/{puuid}` — Get last 5 ranked solo match IDs
- `GET /match/{match_id}?puuid={puuid}` — Get stats for a player in a match
