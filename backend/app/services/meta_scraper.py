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

# --- QWIK STATE DECODER ---
class QwikDecoder:
    """Decodes Lolalytics' Qwik framework JSON state."""
    def __init__(self, pool):
        self.pool = pool
    
    def resolve(self, val):
        if not isinstance(val, str) or not val: return val
        try:
            # Qwik uses base-36 indices to refer to the 'objs' pool
            idx = int(val, 36)
            if 0 <= idx < len(self.pool):
                return self.pool[idx]
        except ValueError:
            pass
        return val

    def resolve_obj(self, obj):
        if not isinstance(obj, dict): return obj
        return {k: self.resolve(v) for k, v in obj.items()}

# --- CONFIG ---
LANES = ["", "top", "jungle", "middle", "bottom", "support"]

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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://lolalytics.com/"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for lane in LANES:
            lane_query = f"&lane={lane}" if lane else ""
            url = f"https://lolalytics.com/lol/tierlist/?tier={rank}&patch=16.8{lane_query}"
            try:
                logger.info("Scraping tierlist: rank=%s, lane=%s", rank, lane or "all")
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200: continue
                html = resp.text

                # Extract Average Tier WR
                if results["tier_avg"] == 50.0:
                    avg_match = re.search(r'Average .*? Win Rate:.*?([0-9\.]+)', html, re.DOTALL | re.IGNORECASE)
                    if avg_match: results["tier_avg"] = float(avg_match.group(1))

                # --- QWIK JSON EXTRACTION ---
                # Lolalytics embeds all data in a qwik/json script tag.
                # Standard HTML parsing only sees 20 rows due to virtualization.
                json_match = re.search(r'<script type="qwik/json">(.*?)</script>', html, re.DOTALL)
                if not json_match:
                    logger.warning("No qwik/json found for %s %s", rank, lane)
                    continue

                try:
                    state = json.loads(json_match.group(1))
                    objs = state.get("objs", [])
                    decoder = QwikDecoder(objs)
                    
                    found_count = 0
                    for raw_obj in objs:
                        if not isinstance(raw_obj, dict): continue
                        
                        # Champion row objects usually have 'wr', 'games', and 'cid' or 'name'
                        # but we resolve indices first to see real values
                        obj = decoder.resolve_obj(raw_obj)
                        
                        # Look for properties that identify a tierlist row
                        # These keys vary but 'wr', 'games', 'rank' are common
                        if "wr" in obj and "games" in obj and ("cid" in obj or "name" in obj):
                            # Resolve name/slug
                            raw_name = obj.get("name") or obj.get("cid")
                            if not isinstance(raw_name, str): continue
                            
                            champ_slug = raw_name.lower().replace("-", "").replace(" ", "").replace("'", "")
                            cid = _CHAMP_ID_MAP.get(champ_slug)
                            if not cid: continue
                            
                            # Resolve Rank: often in 'rank' or 'rank_label' or just index 0
                            rank_label = str(obj.get("rank") or obj.get("rank_label") or "N/A")
                            
                            # Resolve Win Rate & Games
                            # Win rate can be "53.42+1.16", we just want the float
                            try:
                                wr_str = str(obj["wr"])
                                wr_val = float(re.search(r'([0-9\.]+)', wr_str).group(1))
                                
                                games_str = str(obj["games"]).replace(",", "")
                                games_val = int(re.search(r'([0-9]+)', games_str).group(1))
                                
                                tier = str(obj.get("tier") or "N/A")
                                
                                if wr_val > 0 and games_val > 0:
                                    lane_key = lane if lane else "all"
                                    entry_key = f"{cid}:{lane_key}"
                                    
                                    # Deduplication: Keep best record for this rank/lane
                                    if entry_key in results["champions"]:
                                        existing = results["champions"][entry_key]
                                        if games_val > existing["games"] or (existing["rank_label"] == "N/A" and rank_label != "N/A"):
                                            pass 
                                        else:
                                            continue

                                    results["champions"][entry_key] = {
                                        "cid": str(cid),
                                        "name": champ_slug,
                                        "wr": wr_val,
                                        "tier": tier,
                                        "games": games_val,
                                        "lane": lane_key,
                                        "rank_label": rank_label,
                                        "delta": round(wr_val - results["tier_avg"], 2),
                                        "matchups": {},
                                        "last_checked": 0
                                    }
                                    found_count += 1
                            except:
                                continue
                    
                    logger.info("  -> Extracted %d champions from Qwik state.", found_count)
                
                except Exception as je:
                    logger.error("Failed to parse Qwik JSON: %s", je)

                # Minimal sleep between lanes
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error("Error in fetch_rank_meta lane %s for %s: %s", lane, rank, e)
    return results

sync_state = {"active": False, "paused": False, "cancel_requested": False, "mode": "idle"}

def is_sync_active(): return sync_state["active"]
def is_sync_paused(): return sync_state["paused"]
def get_sync_mode(): return sync_state["mode"]

def toggle_pause():
    sync_state["paused"] = not sync_state["paused"]
    return sync_state["paused"]

def cancel_sync():
    if sync_state["active"]:
        sync_state["cancel_requested"] = True
        return True
    return False

async def sync_meta(mode="full"):
    if sync_state["active"]: return False
    sync_state["active"] = True
    sync_state["cancel_requested"] = False
    sync_state["paused"] = False
    sync_state["mode"] = mode
    
    logger.info("Starting Meta Sync (Mode: %s)...", mode)
    try:
        existing = get_meta_data()
        full_meta = existing.get("data", {})
        
        # --- PHASE 1: TIERLIST (FAST) ---
        if mode in ("full", "tierlist"):
            for rank in RANKS:
                if sync_state["cancel_requested"]: break
                while sync_state["paused"] and not sync_state["cancel_requested"]: await asyncio.sleep(1.0)
                
                logger.info("Syncing tierlist: %s", rank)
                rank_data = await fetch_rank_meta(rank)
                if not rank_data: continue
                
                if rank not in full_meta:
                    full_meta[rank] = rank_data
                else:
                    new_champs = rank_data["champions"]
                    old_champs = full_meta[rank].get("champions", {})
                    
                    # 1. Preserve expensive matchup data for champions that still exist
                    for cid, cdata in new_champs.items():
                        if cid in old_champs:
                            cdata["matchups"] = old_champs[cid].get("matchups", {})
                            cdata["last_checked"] = old_champs[cid].get("last_checked", 0)
                    
                    # 2. Replace the entire collection to auto-purge stale/ghost entries
                    full_meta[rank]["tier_avg"] = rank_data["tier_avg"]
                    full_meta[rank]["champions"] = new_champs

            # Save Tierlist immediately
            with open(META_FILE_PATH, "w") as f:
                json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": True}, f, indent=2)
            logger.info("Tierlist Phase Complete.")

        # --- PHASE 2: MATCHUPS (DEEP) ---
        if mode in ("full", "matchups") and not sync_state["cancel_requested"]:
            import random
            sem = asyncio.Semaphore(10)
            now_ts = int(time.time())

            async def crawl_one(rank, cid_str, cdata):
                async with sem:
                    if sync_state["cancel_requested"]: return
                    while sync_state["paused"] and not sync_state["cancel_requested"]: await asyncio.sleep(1.0)
                    
                    # Only crawl if missing or old (24h+)
                    if not cdata.get("matchups") or (now_ts - cdata.get("last_checked", 0)) > 86400:
                        name, lane = cdata["name"], cdata["lane"]
                        logger.info("  -> Crawling matchups: %s (%s) in %s", name, lane, rank)
                        matchups = await fetch_champion_matchups(rank, name, lane)
                        
                        full_meta[rank]["champions"][cid_str]["last_checked"] = now_ts
                        if matchups:
                            full_meta[rank]["champions"][cid_str]["matchups"] = matchups
                        
                        await asyncio.sleep(random.uniform(0.2, 0.8))
                        
                        if random.random() < 0.15: # 15% chance to save
                            with open(META_FILE_PATH, "w") as f:
                                json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": True}, f, indent=2)

            tasks = []
            for rank in RANKS:
                if sync_state["cancel_requested"]: break
                if rank not in full_meta: continue
                champs = full_meta[rank].get("champions", {})
                for cid_str, cdata in champs.items():
                    tasks.append(crawl_one(rank, cid_str, cdata))
            
            if tasks:
                await asyncio.gather(*tasks)
            logger.info("Matchup Phase Complete.")

        if not sync_state["cancel_requested"]:
            with open(META_FILE_PATH, "w") as f:
                json.dump({"updated_at": time.time(), "data": full_meta, "is_partial": False}, f, indent=2)
            logger.info("Sync Process Finished.")

    except Exception as e:
        logger.error("Sync failed: %s", e)
    finally:
        sync_state["active"] = False
        sync_state["mode"] = "idle"
    return True

def get_meta_data() -> dict:
    if not META_FILE_PATH.exists(): return {}
    try:
        with open(META_FILE_PATH, "r") as f: return json.load(f)
    except: return {}
