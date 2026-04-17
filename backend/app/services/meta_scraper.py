import httpx
import asyncio
import json
import logging
import time
from pathlib import Path
from ..state import META_FILE_PATH

logger = logging.getLogger(__name__)

# Lolalytics Rank Mappings
RANKS = [
    "iron", "bronze", "silver", "gold", "platinum", 
    "emerald", "diamond", "master", "grandmaster", "challenger"
]

# We use "current" to always get the latest patch data
BASE_URL = "https://lolalytics.com/data/1.0/tierlist/current/{rank}/"

async def fetch_rank_meta(rank: str) -> dict:
    """Fetch global champion winrates for a specific rank."""
    url = BASE_URL.format(rank=rank)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("Lolalytics fetch failed for %s: %d", rank, resp.status_code)
                return {}
            
            data = resp.json()
            # Lolalytics tierlist JSON structure:
            # { "cid": { "1": [winrate, pickrate, banrate, ...], ... } }
            # Actually, it's often a list or a dict where keys are champion IDs.
            # We'll normalize it to { champion_id: { wr, tier, ... } }
            
            champs = data.get("cid", {})
            result = {}
            for cid, stats in champs.items():
                # Stats is typically a list. Index 0 is often winrate.
                # Note: Lolalytics winrates are often multiplied by 100.
                if isinstance(stats, list) and len(stats) > 0:
                    result[str(cid)] = {
                        "wr": float(stats[0]),
                        "pr": float(stats[1]) if len(stats) > 1 else 0,
                    }
            return result
        except Exception as e:
            logger.error("Error scraping Lolalytics %s: %s", rank, e)
            return {}

async def sync_meta():
    """Cycles through all ranks and updates the local meta file."""
    logger.info("Starting champion meta sync...")
    full_meta = {}
    
    for rank in RANKS:
        logger.info("Syncing meta for rank: %s", rank)
        rank_data = await fetch_rank_meta(rank)
        if rank_data:
            full_meta[rank] = rank_data
        # Sleep to avoid hitting rate limits / being a bad citizen
        await asyncio.sleep(2.0)
    
    if full_meta:
        META_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(META_FILE_PATH, "w") as f:
            json.dump({
                "updated_at": time.time(),
                "data": full_meta
            }, f, indent=2)
        logger.info("Champion meta sync complete. Saved to %s", META_FILE_PATH)
        return True
    return False

def get_meta_data() -> dict:
    """Load the current meta data from disk."""
    if not META_FILE_PATH.exists():
        return {}
    try:
        with open(META_FILE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}
