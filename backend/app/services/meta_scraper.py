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
    "bronze", "silver", "gold", "platinum", "emerald", 
    "diamond", "master", "grandmaster", "challenger"
]

# We use the user-provided URL pattern
BASE_URL = "https://lolalytics.com/lol/tierlist/?tier={rank}&patch=16.8"

# Champion Name -> ID mapping (will be populated from Data Dragon)
_CHAMP_ID_MAP = {}

async def _ensure_champ_ids():
    """Fetch champion name -> id mapping from the latest Data Dragon."""
    global _CHAMP_ID_MAP
    if _CHAMP_ID_MAP:
        return
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Get latest version
            v_resp = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            version = v_resp.json()[0]
            
            # 2. Get champion data
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
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
                if name == "nunu & willump": _CHAMP_ID_MAP["nunu"] = int(val["key"])
                if name == "renata glasc": _CHAMP_ID_MAP["renata"] = int(val["key"])
            logger.info("Loaded %d champion mappings from Data Dragon v%s", len(_CHAMP_ID_MAP), version)
        except Exception as e:
            logger.error("Failed to load Data Dragon: %s", e)

async def fetch_champion_matchups(rank: str, champ_name: str) -> dict:
    """Scrape HTML counter page for a specific champion and rank to get ALL matchup deltas."""
    url = f"https://lolalytics.com/lol/{champ_name.lower()}/counters/?tier={rank}&patch=16.8"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lolalytics.com/"
    }
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return {}
            
            html = resp.text
            matchups = {}
            
            # Exhaustive sweep for all other champions
            for opp_name, opp_cid in _CHAMP_ID_MAP.items():
                if opp_name == champ_name.lower(): continue
                
                # Search for the opponent name and then the winrate percentage
                # Pattern: >Camille< ... 52.66
                pattern = re.compile(rf'>{opp_name.capitalize()}<.*?([34567][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
                match = pattern.search(html)
                
                if match:
                    wr = float(match.group(1))
                    matchups[str(opp_cid)] = wr
                    
            return matchups
        except Exception as e:
            logger.error("Error scraping matchups for %s in %s: %s", champ_name, rank, e)
            return {}

async def fetch_rank_meta(rank: str) -> dict:
    """Scrape HTML tierlist for a specific rank."""
    await _ensure_champ_ids()
    
    url = f"https://lolalytics.com/lol/tierlist/?tier={rank}&patch=16.8"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lolalytics.com/"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("Lolalytics fetch failed for %s: %d", rank, resp.status_code)
                return {}
            
            html = resp.text
            
            # Find the tier average winrate
            avg_wr = 50.0
            avg_match = re.search(r'Average .*? Win Rate:.*?([0-9\.]+)', html, re.DOTALL | re.IGNORECASE)
            if avg_match:
                avg_wr = float(avg_match.group(1))

            results = {"tier_avg": avg_wr, "champions": {}}
            
            # Exhaustive sweep for all champions we know about
            for name, cid in _CHAMP_ID_MAP.items():
                pattern = re.compile(rf'{name}.*?([456][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
                match = pattern.search(html)
                
                if match:
                    wr = float(match.group(1))
                    results["champions"][str(cid)] = {
                        "name": name,
                        "wr": wr,
                        "delta": round(wr - avg_wr, 2),
                        "matchups": {} # Will be populated by the deep sync
                    }
            
            logger.info("Exhaustively scraped %d champions for rank %s", len(results["champions"]), rank)
            return results
        except Exception as e:
            logger.error("Error scraping Lolalytics %s: %s", rank, e)
            return {}

async def sync_meta():
    """Cycles through all ranks and updates the local meta file. Includes deep matchup scraping."""
    logger.info("Starting champion meta sync (Exhaustive HTML Scraper)...")
    full_meta = {}
    
    # 1. Scrape Tierlists (Fast)
    for rank in RANKS:
        logger.info("Syncing tierlist meta for rank: %s", rank)
        rank_data = await fetch_rank_meta(rank)
        if rank_data and rank_data.get("champions"):
            full_meta[rank] = rank_data
        await asyncio.sleep(2.0)
        
    # Save intermediate tierlist data so the UI has *something* while matchups scrape
    if full_meta:
        META_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(META_FILE_PATH, "w") as f:
            json.dump({"updated_at": time.time(), "data": full_meta}, f, indent=2)
            
    # 2. Scrape Deep Matchups (Slow - ~1400 requests)
    logger.info("Starting deep matchup sync for all champions and ranks...")
    
    # We only want to map standard names, not aliases
    standard_names = {cid: name for name, cid in _CHAMP_ID_MAP.items() if len(name) > 2}
    
    for rank in RANKS:
        if rank not in full_meta: continue
        
        # To avoid IP bans, we might just sample a few ranks or do it slowly.
        # But user explicitly requested ALL champions for ALL ranks.
        logger.info("Scraping deep matchups for rank: %s", rank)
        champs_in_rank = full_meta[rank].get("champions", {})
        
        for cid_str, champ_data in champs_in_rank.items():
            name = champ_data["name"]
            logger.info("  -> Scraping matchups for %s in %s", name, rank)
            
            matchups = await fetch_champion_matchups(rank, name)
            if matchups:
                full_meta[rank]["champions"][cid_str]["matchups"] = matchups
            
            # Save incrementally every champion to avoid losing data on crash
            with open(META_FILE_PATH, "w") as f:
                json.dump({"updated_at": time.time(), "data": full_meta}, f, indent=2)
                
            await asyncio.sleep(1.0) # Be nice to the server

    logger.info("Champion deep meta sync complete. Saved to %s", META_FILE_PATH)
    return True

def get_meta_data() -> dict:
    """Load the current meta data from disk."""
    if not META_FILE_PATH.exists():
        return {}
    try:
        with open(META_FILE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}
