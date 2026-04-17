import os
import asyncio
import time
from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
META_FILE_PATH = DATA_DIR / "champion_meta.json"

# Ensure data dir exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Riot Config
RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_REGION = os.getenv("RIOT_REGION", "na1")
RIOT_ROUTING = os.getenv("RIOT_ROUTING", "americas")

# Mapping of platform sub-regions to their respective routing clusters
REGION_TO_ROUTING = {
    "br1": "americas",
    "eun1": "europe",
    "euw1": "europe",
    "jp1": "asia",
    "kr": "asia",
    "la1": "americas",
    "la2": "americas",
    "na1": "americas",
    "oc1": "sea",
    "ph2": "sea",
    "sg2": "sea",
    "th2": "sea",
    "tw2": "sea",
    "vn2": "sea",
    "tr1": "europe",
    "ru": "europe",
}


def get_routing(region: str) -> str:
    """Returns the routing cluster (americas, europe, asia, sea)
    for a given platform region."""
    return REGION_TO_ROUTING.get(region.lower(), "americas")


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
]

RIOT_HEADERS = {"X-Riot-Token": RIOT_API_KEY}


CACHE_VERSION = "v2"


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
route_cache = TTLCache(ttl_seconds=60)   # 1 minute for analyze/history results
enriched_cache = TTLCache(ttl_seconds=3600)  # 1 hour for enriched player stats
match_cache = TTLCache(ttl_seconds=86400)  # 24 hours
