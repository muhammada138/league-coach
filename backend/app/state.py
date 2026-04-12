import os
import asyncio
import time
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

class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self.cache = {}

    def get(self, key):
        if key in self.cache:
            val, expiry = self.cache[key]
            if time.time() < expiry:
                return val
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time() + self.ttl)

    def __contains__(self, key):
        return self.get(key) is not None

    def __getitem__(self, key):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key, value):
        self.set(key, value)

# Global caches for rank lookups and match timelines
rank_cache = TTLCache(ttl_seconds=3600)  # 1 hour
timeline_cache = TTLCache(ttl_seconds=86400)  # 24 hours
route_cache = TTLCache(ttl_seconds=300)  # 5 minutes for analyze/history results
