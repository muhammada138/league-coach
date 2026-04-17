import httpx
import asyncio
import json
import logging
import time
import re
from pathlib import Path
from ..state import META_FILE_PATH

logger = logging.getLogger(__name__)

# Lolalytics Rank Mappings - Aligned with seed tiers in ingestion.py
RANKS = [
    "bronze", "silver", "gold", "platinum", "emerald", 
    "diamond", "master"
]

# Lanes to scrape
LANES = ["top", "jungle", "middle", "bottom", "support"]

# Champion Name -> ID mapping
_CHAMP_ID_MAP = {}
# Champion ID -> Primary Lane (best guess)
_CHAMP_LANE_MAP = {}

async def _ensure_champ_ids():
    global _CHAMP_ID_MAP
    if _CHAMP_ID_MAP: return
    
    async with httpx.AsyncClient() as client:
        try:
            v_resp = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            version = v_resp.json()[0]
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
            resp = await client.get(url)
            data = resp.json()
            for key, val in data.get("data", {}).items():
                name = val["name"].lower()
                clean_name = name.replace(" ", "").replace("'", "").replace(".", "")
                _CHAMP_ID_MAP[clean_name] = int(val["key"])
                _CHAMP_ID_MAP[key.lower()] = int(val["key"])
                
                if name == "wukong": _CHAMP_ID_MAP["monkeyking"] = int(val["key"])
                if name == "nunu & willump": _CHAMP_ID_MAP["nunu"] = int(val["key"])
                if name == "renata glasc": _CHAMP_ID_MAP["renata"] = int(val["key"])
            logger.info("Loaded %d champion mappings", len(_CHAMP_ID_MAP))
        except Exception as e:
            logger.error("Failed to load Data Dragon: %s", e)

async def fetch_champion_matchups(rank: str, champ_name: str, lane: str) -> dict:
    """Scrape HTML counter page for a specific champion, rank, AND lane."""
    # Example: https://lolalytics.com/lol/aatrox/counters/?lane=top&tier=emerald&patch=16.8
    url = f"https://lolalytics.com/lol/{champ_name.lower()}/counters/?lane={lane}&tier={rank}&patch=16.8"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lolalytics.com/"
    }
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200: return {}
            
            html = resp.text
            matchups = {}
            
            # Pattern: Opponent Name followed by winrate
            # The HTML has a VS block for each counter
            for opp_name, opp_cid in _CHAMP_ID_MAP.items():
                if opp_name == champ_name.lower() or len(opp_name) < 3: continue
                
                # We look for the opponent name capitalized then a VS winrate decimal
                pattern = re.compile(rf'>{opp_name.capitalize()}<.*?([34567][0-9]\.[0-9]+)<!---->%<div class="text-cyan-200">VS</div>', re.IGNORECASE | re.DOTALL)
                match = pattern.search(html)
                
                if match:
                    wr = float(match.group(1))
                    matchups[str(opp_cid)] = wr
                    
            return matchups
        except Exception as e:
            logger.error("Error scraping %s matchups for %s: %s", lane, champ_name, e)
            return {}

async def fetch_rank_meta(rank: str) -> dict:
    """Scrape tierlists to identify which champions play which lanes."""
    await _ensure_champ_ids()
    results = {"tier_avg": 50.0, "champions": {}}
    
    # We scrape the main tierlist for the rank to get initial WRs and lane associations
    url = f"https://lolalytics.com/lol/tierlist/?tier={rank}&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://lolalytics.com/"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200: return {}
            html = resp.text
            
            avg_wr = 50.0
            avg_match = re.search(r'Average .*? Win Rate:.*?([0-9\.]+)', html, re.DOTALL | re.IGNORECASE)
            if avg_match: avg_wr = float(avg_match.group(1))
            results["tier_avg"] = avg_wr

            # Exhaustive sweep for all champions we know about
            for clean_name, cid in _CHAMP_ID_MAP.items():
                if len(clean_name) < 3: continue
                
                # Anchor to the specific build link for this champion to avoid confusion
                # Then skip ahead to the winrate column (q:key="5")
                # Pattern: /lol/vayne/build/ ... q:key="5" ... >51.99
                pattern = re.compile(rf'/lol/{clean_name}/build/.*?q:key="5".*?>([456][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
                match = pattern.search(html)
                
                if match:
                    wr = float(match.group(1))
                    results["champions"][str(cid)] = {
                        "name": clean_name,
                        "wr": wr,
                        "lane": "unknown",
                        "delta": round(wr - avg_wr, 2),
                        "matchups": {}
                    }
                    
                    # Also find the lane icon nearby
                    # Pattern: /lol/vayne/build/ ... alt="bottom lane"
                    lane_match = re.search(rf'/lol/{clean_name}/build/.*?alt="(\w+) lane"', html, re.IGNORECASE | re.DOTALL)
                    if lane_match:
                        results["champions"][str(cid)]["lane"] = lane_match.group(1).lower()
            return results
        except Exception as e:
            logger.error("Error in fetch_rank_meta for %s: %s", rank, e)
            return {}

# ---------------------------------------------------------------------------
# Global sync control
# ---------------------------------------------------------------------------
_sync_active = False
_cancel_requested = False

async def sync_meta():
    """Daily sync: Performs incremental updates to meta data, only scraping missing matchups."""
    global _sync_active, _cancel_requested
    if _sync_active: return False
    
    _sync_active = True
    _cancel_requested = False
    logger.info("Starting Incremental Meta Sync...")
    
    try:
        # Load existing data first
        existing = get_meta_data()
        full_meta = existing.get("data", {})
        
        # 1. Update Tierlist Global Stats (Always fast, ensures we see new champs)
        for rank in RANKS:
            if _cancel_requested: break
            logger.info("Updating global stats for rank: %s", rank)
            rank_data = await fetch_rank_meta(rank)
            
            if rank_data and rank_data.get("champions"):
                if rank not in full_meta:
                    full_meta[rank] = rank_data
                else:
                    # Merge: keep existing matchups, update current stats
                    full_meta[rank]["tier_avg"] = rank_data["tier_avg"]
                    for cid, cdata in rank_data["champions"].items():
                        if cid not in full_meta[rank]["champions"]:
                            full_meta[rank]["champions"][cid] = cdata
                        else:
                            # Update WR/Delta but keep existing matchups
                            full_meta[rank]["champions"][cid]["wr"] = cdata["wr"]
                            full_meta[rank]["champions"][cid]["delta"] = cdata["delta"]
                            full_meta[rank]["champions"][cid]["lane"] = cdata["lane"]

        # 2. Fill Missing Matchups (The slow part)
        import random
        for rank in RANKS:
            if _cancel_requested: break
            if rank not in full_meta: continue
            
            champs = full_meta[rank].get("champions", {})
            for cid_str, cdata in champs.items():
                if _cancel_requested: break
                
                # ONLY scrape if matchups are missing or empty
                if not cdata.get("matchups"):
                    name, lane = cdata["name"], cdata["lane"]
                    logger.info("  -> Filling missing matchups: %s (%s) in %s", name, lane, rank)
                    
                    matchups = await fetch_champion_matchups(rank, name, lane)
                    if matchups:
                        full_meta[rank]["champions"][cid_str]["matchups"] = matchups
                        # Incremental save
                        with open(META_FILE_PATH, "w") as f:
                            json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": True}, f, indent=2)
                    
                    # Slower scraping with jitter
                    await asyncio.sleep(random.uniform(4.0, 8.0))
                else:
                    # Skip already scraped champion
                    continue

        if not _cancel_requested:
            with open(META_FILE_PATH, "w") as f:
                json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": False}, f, indent=2)
            logger.info("Incremental Sync Complete.")
        else:
            logger.info("Incremental Sync HALTED by user.")
            
    finally:
        _sync_active = False
        _cancel_requested = False
    return True

def cancel_sync():
    global _cancel_requested
    if _sync_active:
        _cancel_requested = True
        return True
    return False

def is_sync_active():
    return _sync_active

def get_meta_data() -> dict:
    if not META_FILE_PATH.exists(): return {}
    try:
        with open(META_FILE_PATH, "r") as f: return json.load(f)
    except: return {}
