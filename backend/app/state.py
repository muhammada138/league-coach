import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_REGION = os.getenv("RIOT_REGION", "na1")
RIOT_ROUTING = os.getenv("RIOT_ROUTING", "americas")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")]

RIOT_HEADERS = {"X-Riot-Token": RIOT_API_KEY}

# Global semaphore to limit concurrent requests to the Riot API (prevents 429 Too Many Requests)
api_semaphore = asyncio.Semaphore(15)

# Simple in-memory TTL cache
_cache: dict = {}
_CACHE_TTL = 300

# Global cache for rank lookups
rank_cache = {}
