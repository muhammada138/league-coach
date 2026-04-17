import httpx
import asyncio
import json
import logging
import time
import re
from pathlib import Path
from ..state import META_FILE_PATH, sync_state

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

async def _ensure_champ_ids():
    """Fetch champion name -> id mapping from the latest Data Dragon."""
    global _CHAMP_ID_MAP
    if _CHAMP_ID_MAP:
        return
    
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
            logger.info("Loaded %d champion mappings from Data Dragon v%s", len(_CHAMP_ID_MAP), version)
        except Exception as e:
            logger.error("Failed to load Data Dragon: %s", e)

async def fetch_champion_matchups(rank: str, champ_name: str, lane: str) -> dict:
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
            for opp_name, opp_cid in _CHAMP_ID_MAP.items():
                if opp_name == champ_name.lower() or len(opp_name) < 3: continue
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
    await _ensure_champ_ids()
    results = {"tier_avg": 50.0, "champions": {}}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://lolalytics.com/"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for lane in LANES:
            url = f"https://lolalytics.com/lol/tierlist/?lane={lane}&tier={rank}&patch=16.8"
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200: continue
                html = resp.text

                if results["tier_avg"] == 50.0:
                    avg_match = re.search(r'Average .*? Win Rate:.*?([0-9\.]+)', html, re.DOTALL | re.IGNORECASE)
                    if avg_match: results["tier_avg"] = float(avg_match.group(1))

                # Isolate the data rows using a more robust pattern
                # Every row starts with a build link
                rows = re.split(r'href="/lol/([^/"]+)/build/\??[^"]*"', html)

                # re.split with a capturing group returns [pre, group, post, pre, group, post...]
                # so index 1 is name, index 2 is the row content, etc.
                for i in range(1, len(rows), 2):
                    clean_name = rows[i].lower().replace("-", "")
                    row_content = rows[i+1][:2000] # Limit search to the row area

                    cid = _CHAMP_ID_MAP.get(clean_name)
                    if not cid: continue

                    # Target the Win Rate column (q:key="5") specifically
                    # Text usually looks like: ...q:key="5"><div...>51.99</div>...
                    wr_match = re.search(r'q:key="5".*?>([0-9\.]+)', row_content, re.DOTALL)

                    if wr_match:
                        wr = float(wr_match.group(1))
                        if str(cid) not in results["champions"]:
                            results["champions"][str(cid)] = {
                                "name": clean_name,
                                "wr": wr,
                                "lane": lane,
                                "delta": round(wr - results["tier_avg"], 2),
                                "matchups": {},
                                "last_checked": 0
                            }

                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error("Error in fetch_rank_meta lane %s for %s: %s", lane, rank, e)
    return results

def is_sync_active(): return sync_state["active"]
def is_sync_paused(): return sync_state["paused"]
def toggle_pause():
    sync_state["paused"] = not sync_state["paused"]
    return sync_state["paused"]
def cancel_sync():
    if sync_state["active"]:
        sync_state["cancel_requested"] = True
        return True
    return False

async def sync_meta():
    if sync_state["active"]: return False
    sync_state["active"] = True
    sync_state["cancel_requested"] = False
    sync_state["paused"] = False
    logger.info("Starting Role-Aware Meta Sync...")
    try:
        existing = get_meta_data()
        full_meta = existing.get("data", {})
        for rank in RANKS:
            if sync_state["cancel_requested"]: break
            while sync_state["paused"] and not sync_state["cancel_requested"]: await asyncio.sleep(1.0)
            logger.info("Syncing tierlist: %s", rank)
            rank_data = await fetch_rank_meta(rank)
            if not rank_data: continue
            if rank not in full_meta:
                full_meta[rank] = rank_data
            else:
                full_meta[rank]["tier_avg"] = rank_data["tier_avg"]
                for cid, cdata in rank_data["champions"].items():
                    if cid not in full_meta[rank]["champions"]:
                        full_meta[rank]["champions"][cid] = cdata
                    else:
                        full_meta[rank]["champions"][cid]["wr"] = cdata["wr"]
                        full_meta[rank]["champions"][cid]["delta"] = cdata["delta"]
                        full_meta[rank]["champions"][cid]["lane"] = cdata["lane"]
        import random
        now_ts = int(time.time())
        for rank in RANKS:
            if sync_state["cancel_requested"]: break
            if rank not in full_meta: continue
            champs = full_meta[rank].get("champions", {})
            for cid_str, cdata in champs.items():
                if sync_state["cancel_requested"]: break
                while sync_state["paused"] and not sync_state["cancel_requested"]: await asyncio.sleep(1.0)
                if not cdata.get("matchups") and (now_ts - cdata.get("last_checked", 0)) > 86400:
                    name, lane = cdata["name"], cdata["lane"]
                    logger.info("  -> Crawling matchups: %s (%s) in %s", name, lane, rank)
                    matchups = await fetch_champion_matchups(rank, name, lane)
                    full_meta[rank]["champions"][cid_str]["last_checked"] = now_ts
                    if matchups:
                        full_meta[rank]["champions"][cid_str]["matchups"] = matchups
                    if int(cid_str) % 5 == 0:
                        with open(META_FILE_PATH, "w") as f:
                            json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": True}, f, indent=2)
                    await asyncio.sleep(random.uniform(4.0, 8.0))
        if not sync_state["cancel_requested"]:
            with open(META_FILE_PATH, "w") as f:
                json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": False}, f, indent=2)
            logger.info("Incremental Sync Complete.")
    finally:
        sync_state["active"] = False
        sync_state["cancel_requested"] = False
        sync_state["paused"] = False
    return True

def get_meta_data() -> dict:
    if not META_FILE_PATH.exists(): return {}
    try:
        with open(META_FILE_PATH, "r") as f: return json.load(f)
    except: return {}
