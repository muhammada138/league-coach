import httpx
import asyncio
import json
import logging
import time
import re
from pathlib import Path
from ..state import META_FILE_PATH

logger = logging.getLogger(__name__)

# Lolalytics Rank Mappings
RANKS = [
    "iron", "bronze", "silver", "gold", "platinum", 
    "emerald", "diamond", "master", "grandmaster", "challenger"
]

# We use the user-provided URL pattern
BASE_URL = "https://lolalytics.com/lol/tierlist/?tier={rank}&patch=16.8"

# Champion Name -> ID mapping (will be populated from Data Dragon)
_CHAMP_ID_MAP = {}

async def _ensure_champ_ids():
    """Fetch champion name -> id mapping from Data Dragon if not already loaded."""
    global _CHAMP_ID_MAP
    if _CHAMP_ID_MAP:
        return
    
    url = "https://ddragon.leagueoflegends.com/cdn/14.5.1/data/en_US/champion.json"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
            data = resp.json()
            for key, val in data.get("data", {}).items():
                name = val["name"].lower()
                # Remove spaces, dots, and apostrophes for matching
                clean_name = name.replace(" ", "").replace("'", "").replace(".", "")
                _CHAMP_ID_MAP[clean_name] = int(val["key"])
                # Also store the key itself (internal ID name)
                _CHAMP_ID_MAP[key.lower()] = int(val["key"])
                
                # Special cases for Lolalytics URL names
                if name == "wukong": _CHAMP_ID_MAP["monkeyking"] = int(val["key"])
                if name == "leblanc": _CHAMP_ID_MAP["leblanc"] = int(val["key"])
                if name == "nunu & willump": _CHAMP_ID_MAP["nunu"] = int(val["key"])
                if name == "renata glasc": _CHAMP_ID_MAP["renata"] = int(val["key"])
            logger.info("Loaded %d champion mappings", len(_CHAMP_ID_MAP))
        except Exception as e:
            logger.error("Failed to load Data Dragon: %s", e)

async def fetch_rank_meta(rank: str) -> dict:
    """Scrape HTML tierlist for a specific rank."""
    await _ensure_champ_ids()
    
    # User confirmed patch 16.8
    url = f"https://lolalytics.com/lol/tierlist/?tier={rank}&patch=16.8"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://lolalytics.com/"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("Lolalytics fetch failed for %s: %d", rank, resp.status_code)
                return {}
            
            html = resp.text
            
            # Find champion names from their build links
            # Example: href="/lol/sona/build/"
            champ_names = re.findall(r'href="/lol/([^/"]+)/build/', html)
            champ_names = list(dict.fromkeys(champ_names)) # unique
            
            results = {}
            for name in champ_names:
                # Map name to ID
                cid = _CHAMP_ID_MAP.get(name.lower().replace("-", ""))
                if not cid: continue
                
                # Search for the winrate near the champion name link
                # Pattern: we look for the name in the text, then the next occurrence of a decimal (winrate)
                # Lolalytics typically shows WR as "52.66" or similar
                # We'll use a regex that looks for the name followed by stats
                pattern = re.compile(rf'>{name.capitalize()}<.*?Win\s*([0-9\.]+)', re.IGNORECASE | re.DOTALL)
                match = pattern.search(html)
                if not match:
                    # Try a simpler decimal search near the name
                    pattern = re.compile(rf'{name}.*?([456][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
                    match = pattern.search(html)

                if match:
                    results[str(cid)] = {
                        "wr": float(match.group(1)),
                        "pr": 0.0 
                    }
            
            logger.info("Scraped %d champions for rank %s", len(results), rank)
            return results
        except Exception as e:
            logger.error("Error scraping Lolalytics %s: %s", rank, e)
            return {}

async def sync_meta():
    """Cycles through all ranks and updates the local meta file."""
    logger.info("Starting champion meta sync (HTML Scraper)...")
    full_meta = {}
    
    for rank in RANKS:
        logger.info("Syncing meta for rank: %s", rank)
        rank_data = await fetch_rank_meta(rank)
        if rank_data:
            full_meta[rank] = rank_data
        # Sleep to avoid hitting rate limits
        await asyncio.sleep(5.0)
    
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
