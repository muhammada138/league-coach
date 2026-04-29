import httpx
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from ..state import META_FILE_PATH, sync_state, DATA_DIR

logger = logging.getLogger(__name__)
_CACHED_FULL_VERSION = None
_VERSION_CACHE_TIME = 0

# Configuration Constants
VERSION_CACHE_DURATION = 12 * 3600  # 12 hours
TIERLIST_REFRESH_THRESHOLD = 43200  # 12 hours
MATCHUP_STALE_THRESHOLD = 86400      # 24 hours
SCRAPE_DELAY_LANE_SEC = 0.05
SCRAPE_DELAY_MATCHUP_SEC = 0.15
SYNC_PAUSE_POLL_SEC = 1.0
SAVE_PROBABILITY = 0.03

# Per-champion game threshold before new-patch WR is trusted
MIN_GAMES_TRUSTED = 200
# Lower bar for niche/off-meta champions
MIN_GAMES_NICHE = 30

# Patch snapshot directory
PATCH_SNAPSHOT_DIR = DATA_DIR / "patch_snapshots"
PATCH_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

async def _get_latest_version_full() -> str:
    """Fetch the latest full LoL version from Data Dragon with caching."""
    global _CACHED_FULL_VERSION, _VERSION_CACHE_TIME
    now = time.time()
    
    if _CACHED_FULL_VERSION and (now - _VERSION_CACHE_TIME) < VERSION_CACHE_DURATION:
        return _CACHED_FULL_VERSION

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if resp.status_code == 200:
                versions = resp.json()
                if versions:
                    _CACHED_FULL_VERSION = versions[0]
                    _VERSION_CACHE_TIME = now
                    return _CACHED_FULL_VERSION
    except Exception as e:
        logger.error("Failed to fetch latest version: %s", e)
            
    return _CACHED_FULL_VERSION or "14.8.1"

async def get_patch_at_offset(offset: int = 0) -> str:
    """Fetch a patch version (major.minor) from Data Dragon by index (0=current, 1=prev)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if resp.status_code == 200:
                versions = resp.json()
                if len(versions) > offset:
                    full_v = versions[offset]
                    parts = full_v.split(".")
                    if len(parts) >= 2:
                        return f"{parts[0]}.{parts[1]}"
    except Exception as e:
        logger.error("Failed to fetch patch at offset %d: %s", offset, e)
    return "14.8" # Fallback

async def get_current_patch() -> str:
    return await get_patch_at_offset(0)

# Lolalytics Rank Mappings - Aligned with seed tiers in ingestion.py
RANKS = [
    "bronze", "silver", "gold", "platinum", "emerald", 
    "diamond", "master"
]

# --- CONFIG ---
LANES = ["", "top", "jungle", "middle", "bottom", "support"]
# Pin matchup data to a specific patch (new patches often have bad sample sizes).
# Set to None to always use the current live patch.
MATCHUP_PATCH_OVERRIDE = None

_TIER_LABELS = {
    1: "S+", 2: "S", 3: "S-",
    4: "A+", 5: "A", 6: "A-",
    7: "B+", 8: "B", 9: "B-",
    10: "C+", 11: "C", 12: "C-",
    13: "D+", 14: "D", 15: "D-",
}

# Champion Name -> ID mapping
_CHAMP_ID_MAP = {}
_ID_CHAMP_MAP = {} # CID string -> {id, name, slug}

# In-memory cache for meta data to avoid expensive synchronous I/O
_META_CACHE = None
_META_LAST_MOD = 0

async def _ensure_champ_ids():
    """Fetch champion name -> id mapping from the latest Data Dragon."""
    global _CHAMP_ID_MAP, _ID_CHAMP_MAP
    if _CHAMP_ID_MAP:
        return
    
    version = await _get_latest_version_full()
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200: return
            data = resp.json()
            for key, val in data.get("data", {}).items():
                cid = val["key"]
                name = val["name"]
                slug = key.lower().replace(" ", "").replace("'", "")
                
                _CHAMP_ID_MAP[slug] = int(cid)
                _ID_CHAMP_MAP[str(cid)] = {"id": int(cid), "name": name, "slug": slug}
                
            logger.info("Champion ID maps initialized: %d champions", len(_CHAMP_ID_MAP))
        except Exception as e:
            logger.error("Failed to fetch champion IDs: %s", e)

async def fetch_champion_matchups(rank: str, champ_name: str, lane: str, patch: str = None) -> dict:
    """Returns {opp_cid_str: {'wr': float, 'games': int}} via Qwik state extraction."""
    if not patch:
        patch = MATCHUP_PATCH_OVERRIDE or await get_current_patch()
        
    lane_param = f"&lane={lane}" if lane and lane != "all" else ""
    url = f"https://lolalytics.com/lol/{champ_name.lower()}/counters/?tier={rank}&patch={patch}{lane_param}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lolalytics.com/"
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200: return {}
            html = resp.text

            json_match = re.search(r'<script type="qwik/json">(.*?)</script>', html, re.DOTALL)
            if not json_match: return {}

            state = json.loads(json_match.group(1))
            objs = state.get("objs", [])
            n = len(objs)

            def _res(val):
                if not isinstance(val, str): return val
                try:
                    idx = int(val, 36)
                    if 0 <= idx < n: return objs[idx]
                except (ValueError, TypeError): pass
                return val

            # Greedy Extraction: Scan all objects for matchup signatures (cid + vsWr)
            matchups = {}
            for obj in objs:
                # Some matchups are nested in lists, others are flat in the objs array.
                # We harvest anything with a 'cid' and 'vsWr'.
                candidate = None
                if isinstance(obj, dict) and "cid" in obj and "vsWr" in obj:
                    candidate = obj
                
                if candidate:
                    try:
                        cid_val = _res(candidate.get("cid"))
                        if cid_val is None: continue
                        
                        cid_str = str(int(float(cid_val)))
                        wr_val = float(_res(candidate["vsWr"]))
                        games_val = int(_res(candidate.get("n", 0)) or 0)
                        
                        if wr_val > 0:
                            # Keep highest game count version if duplicates exist in state
                            if cid_str not in matchups or games_val > matchups[cid_str]["games"]:
                                matchups[cid_str] = {"wr": wr_val, "games": games_val}
                    except (ValueError, TypeError, KeyError):
                        continue
                
                # Also check lists of references as a fallback
                elif isinstance(obj, list) and len(obj) > 3:
                     for ref in obj:
                        entry = _res(ref)
                        if isinstance(entry, dict) and "cid" in entry and "vsWr" in entry:
                            try:
                                cid_val = _res(entry.get("cid"))
                                if cid_val is None: continue
                                cid_str = str(int(float(cid_val)))
                                wr_val = float(_res(entry["vsWr"]))
                                games_val = int(_res(entry.get("n", 0)) or 0)
                                if wr_val > 0:
                                    if cid_str not in matchups or games_val > matchups[cid_str]["games"]:
                                        matchups[cid_str] = {"wr": wr_val, "games": games_val}
                            except: continue

            if not matchups:
                logger.warning("No matchups extracted for %s (%s) in %s", champ_name, lane, rank)
            else:
                logger.info("  -> Extracted %d unique matchups.", len(matchups))

            return matchups
        except Exception as e:
            logger.error("Error scraping %s matchups for %s: %s", lane, champ_name, e)
            return {}

async def fetch_rank_meta(rank: str, patch: str = None) -> dict:
    await _ensure_champ_ids()
    if not patch:
        patch = await get_current_patch()
    results = {"tier_avg": 50.0, "champions": {}}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://lolalytics.com/"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for lane in LANES:
            lane_query = f"&lane={lane}" if lane else ""
            url = f"https://lolalytics.com/lol/tierlist/?tier={rank}&patch={patch}{lane_query}"
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
                    n = len(objs)

                    def _res(val):
                        """Resolve a base-36 reference string to its pool value."""
                        if not isinstance(val, str):
                            return val
                        try:
                            idx = int(val, 36)
                            if 0 <= idx < n:
                                return objs[idx]
                        except (ValueError, TypeError):
                            pass
                        return val

                    found_count = 0
                    for raw in objs:
                        # Component objects link a champion (cid) to a stats row (row)
                        if not isinstance(raw, dict) or "row" not in raw or "cid" not in raw:
                            continue
                        try:
                            # 1. Resolve champion ID (cid is a base-36 ref → numeric ID)
                            cid_val = _res(raw["cid"])
                            try:
                                cid_str = str(int(cid_val))
                            except (ValueError, TypeError):
                                continue
                            champ_info = _ID_CHAMP_MAP.get(cid_str)
                            if not champ_info:
                                continue

                            cid = champ_info["id"]
                            champ_slug = champ_info["slug"]

                            # 2. Resolve stats object (row is a base-36 index into objs)
                            row_idx = int(raw["row"], 36)
                            if row_idx >= n:
                                continue
                            stats_raw = objs[row_idx]
                            if not isinstance(stats_raw, dict) or "wr" not in stats_raw:
                                continue

                            # 3. Resolve each stat value one level from the stats object
                            wr_val = _res(stats_raw["wr"])
                            games_val = _res(stats_raw["games"])
                            tier_raw = _res(stats_raw.get("tier", ""))
                            try:
                                tier = _TIER_LABELS.get(int(tier_raw), "N/A")
                            except (ValueError, TypeError):
                                tier = str(tier_raw) if tier_raw else "N/A"
                            rank_label = str(_res(stats_raw.get("rank", "")) or "N/A")

                            wr_float = float(wr_val)
                            games_int = int(str(games_val).replace(",", ""))

                            if wr_float > 0 and games_int > 0:
                                real_lane = str(_res(stats_raw.get("lane", "")) or "")
                                if not real_lane:
                                    real_lane = lane if lane else "all"
                                    
                                lane_key = real_lane
                                entry_key = f"{cid}:{lane_key}"
                                is_strict = (lane is None)

                                # Deduplication: prefer strict (global pass) to avoid fluff games.
                                # If we already have a strict entry, do not overwrite it with the relaxed lane-specific query.
                                if entry_key in results["champions"]:
                                    existing = results["champions"][entry_key]
                                    if existing.get("is_strict") and not is_strict:
                                        continue
                                    if not existing.get("is_strict") and not is_strict:
                                        if not (games_int > existing["games"] or (existing["rank_label"] == "N/A" and rank_label != "N/A")):
                                            continue

                                results["champions"][entry_key] = {
                                    "cid": str(cid),
                                    "name": champ_slug,
                                    "wr": wr_float,
                                    "tier": tier,
                                    "games": games_int,
                                    "lane": lane_key,
                                    "real_lane": real_lane,
                                    "rank_label": rank_label,
                                    "delta": round(wr_float - results["tier_avg"], 2),
                                    "matchups": {},
                                    "last_checked": 0,
                                    "is_strict": is_strict
                                }
                                found_count += 1
                        except Exception:
                            continue

                    logger.info("  -> Extracted %d champions from Qwik state.", found_count)

                except Exception as je:
                    logger.error("Failed to parse Qwik JSON: %s", je)

                # Brief delay between lane requests
                await asyncio.sleep(SCRAPE_DELAY_LANE_SEC)

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

async def sync_meta(mode="full", tierlist_patch: str = None, matchup_patch: str = None):
    if sync_state["active"]: return False
    sync_state["active"] = True
    sync_state["cancel_requested"] = False
    sync_state["paused"] = False
    sync_state["mode"] = mode
    
    logger.info("Starting Meta Sync (Mode: %s, tierlist_patch=%s, matchup_patch=%s)...", mode, tierlist_patch, matchup_patch)
    try:
        current_patch  = tierlist_patch or await get_patch_at_offset(0)
        mu_patch = matchup_patch or await get_patch_at_offset(1)
        
        existing = get_meta_data()
        full_meta = existing.get("data", {})
        last_synced_patch = existing.get("synced_patch", None)
        
        # --- PATCH TRANSITION DETECTION ---
        # If the targeted patch is different from the last synced patch, snapshot the old data
        if last_synced_patch and last_synced_patch != current_patch:
            if full_meta:
                logger.info("Patch transition detected: %s -> %s. Snapshotting outgoing data.", last_synced_patch, current_patch)
                save_patch_snapshot(last_synced_patch, full_meta)
            # We are syncing a brand new patch, we MUST clear old data to prevent bleeding 16.8 into 16.9
            full_meta = {}
        
        # Ensure we have tierlist data before doing matchups
        needs_tierlist = not full_meta or mode in ("full", "tierlist")
        if mode == "full" and full_meta and (int(time.time()) - existing.get("tierlist_updated", 0)) < TIERLIST_REFRESH_THRESHOLD:
            logger.info("Tierlist fetched recently (<12h). Skipping Phase 1.")
            needs_tierlist = False

        # --- PHASE 1: TIERLIST (FAST) ---
        if needs_tierlist:
            for rank in RANKS:
                if sync_state["cancel_requested"]: break
                while sync_state["paused"] and not sync_state["cancel_requested"]: await asyncio.sleep(SYNC_PAUSE_POLL_SEC)
                
                logger.info("Syncing tierlist: %s (Patch %s)", rank, current_patch)
                rank_data = await fetch_rank_meta(rank, patch=current_patch)
                if not rank_data: continue
                
                if rank not in full_meta:
                    full_meta[rank] = rank_data
                else:
                    new_champs = rank_data["champions"]
                    old_champs = full_meta[rank].get("champions", {})
                    
                    # Preserve expensive matchup data from existing entries
                    for cid, cdata in new_champs.items():
                        if cid in old_champs:
                            old_data = old_champs[cid]
                            cdata["matchups"] = old_data.get("matchups", {})
                            cdata["last_checked"] = old_data.get("last_checked", 0)
                        old_champs[cid] = cdata
                    
                    full_meta[rank]["tier_avg"] = rank_data["tier_avg"]
                    full_meta[rank]["champions"] = old_champs

            # Save Tierlist immediately
            existing["tierlist_updated"] = int(time.time())
            existing["synced_patch"] = current_patch
            save_meta_data({"tierlist_updated": existing["tierlist_updated"], "synced_patch": current_patch, "updated_at": time.time(), "data": full_meta, "is_partial": True})
            logger.info("Tierlist Phase Complete.")
            
        # --- PHASE 2: MATCHUPS (DEEP) ---
        if mode in ("full", "matchups") and not sync_state["cancel_requested"]:
            import random
            sem = asyncio.Semaphore(3)
            now_ts = int(time.time())

            async def crawl_one(rank, cid_str, cdata):
                async with sem:
                    if sync_state["cancel_requested"]: return
                    while sync_state["paused"] and not sync_state["cancel_requested"]: await asyncio.sleep(SYNC_PAUSE_POLL_SEC)
                    
                    # Force re-crawl on explicit matchups mode or if human explicitly set matchup_patch; otherwise skip if fresh (<24h)
                    stale = (now_ts - cdata.get("last_checked", 0)) > MATCHUP_STALE_THRESHOLD
                    name, lane = cdata["name"], cdata["lane"]
                    
                    if lane == "all": return # Skip "all" lane to save massive time; we only need specific lane matchups

                    if mode == "matchups" or matchup_patch is not None or stale:
                        try:
                            logger.info("  -> Crawling matchups: %s (%s) in %s (Patch %s)", name, lane, rank, mu_patch)
                            matchups = await fetch_champion_matchups(rank, name, lane, patch=mu_patch)
                            
                            full_meta[rank]["champions"][cid_str]["last_checked"] = now_ts
                            if matchups:
                                full_meta[rank]["champions"][cid_str]["matchups"] = matchups
                            
                            await asyncio.sleep(SCRAPE_DELAY_MATCHUP_SEC)
                            
                            if random.random() < SAVE_PROBABILITY:
                                save_meta_data({"tierlist_updated": existing.get("tierlist_updated", 0), "synced_patch": current_patch, "updated_at": time.time(), "data": full_meta, "is_partial": True})
                        except Exception as e:
                            logger.error("  -> Failed to crawl %s (%s) in %s: %s", name, lane, rank, e)

            tasks = []
            for rank in RANKS:
                if sync_state["cancel_requested"]: break
                if rank not in full_meta: continue
                champs = full_meta[rank].get("champions", {})
                for cid_str, cdata in champs.items():
                    tasks.append(crawl_one(rank, cid_str, cdata))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Matchup Phase Complete.")

        if not sync_state["cancel_requested"]:
            save_meta_data({"tierlist_updated": existing.get("tierlist_updated", 0), "synced_patch": current_patch, "updated_at": time.time(), "data": full_meta, "is_partial": False})
            
            # Auto-snapshot completed data for the patch we just synced
            save_patch_snapshot(current_patch, full_meta)
            
            # Write completion marker so scheduler knows the daily sync finished successfully
            if mode == "full":
                try:
                    import datetime
                    with open(DATA_DIR / ".last_full_sync", "w") as f:
                        f.write(datetime.datetime.utcnow().strftime("%Y-%m-%d"))
                except: pass

            logger.info("Sync Process Finished.")

    except Exception as e:
        logger.error("Sync failed: %s", e)
    finally:
        sync_state["active"] = False
        sync_state["mode"] = "idle"
    return True

def save_meta_data(data_dict: dict):
    global _META_CACHE, _META_LAST_MOD
    tmp_path = str(META_FILE_PATH) + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data_dict, f, indent=2)
    os.replace(tmp_path, META_FILE_PATH)

    # Update cache immediately to maintain consistency
    _META_CACHE = data_dict
    try:
        _META_LAST_MOD = os.path.getmtime(META_FILE_PATH)
    except Exception:
        _META_LAST_MOD = time.time()

def get_meta_data() -> dict:
    global _META_CACHE, _META_LAST_MOD
    if not META_FILE_PATH.exists():
        return {}

    try:
        # Check modification time to see if we can use the cache
        mtime = META_FILE_PATH.stat().st_mtime
        if _META_CACHE is not None and mtime <= _META_LAST_MOD:
            return _META_CACHE

        with open(META_FILE_PATH, "r") as f:
            data = json.load(f)
            _META_CACHE = data
            _META_LAST_MOD = mtime
            return data
    except Exception as e:
        logger.error("Failed to load meta data: %s", e)
        return _META_CACHE if _META_CACHE is not None else {}


# ---------------------------------------------------------------------------
# Patch Snapshot System
# ---------------------------------------------------------------------------

def save_patch_snapshot(patch: str, rank_data: dict) -> None:
    """Save a snapshot of tierlist data for a specific patch version."""
    snapshot_path = PATCH_SNAPSHOT_DIR / f"{patch}.json"
    tmp_path = str(snapshot_path) + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump({"patch": patch, "saved_at": time.time(), "data": rank_data}, f)
        os.replace(tmp_path, snapshot_path)
        logger.info("Saved patch snapshot: %s", patch)
    except Exception as e:
        logger.error("Failed to save patch snapshot %s: %s", patch, e)


def load_patch_snapshot(patch: str) -> dict:
    """Load a previously saved patch snapshot. Returns empty dict if not found."""
    snapshot_path = PATCH_SNAPSHOT_DIR / f"{patch}.json"
    if not snapshot_path.exists():
        return {}
    try:
        with open(snapshot_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load patch snapshot %s: %s", patch, e)
        return {}


def list_saved_patches() -> list[str]:
    """List all patch versions that have saved snapshots, sorted newest-first."""
    patches = []
    for f in PATCH_SNAPSHOT_DIR.glob("*.json"):
        patches.append(f.stem)
    # Sort by major.minor numerically
    def _sort_key(p):
        try:
            parts = p.split(".")
            return (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return (0, 0)
    return sorted(patches, key=_sort_key, reverse=True)


async def get_available_patches() -> list[str]:
    """Return a list of recent patch versions from Data Dragon (last 6)."""
    patches = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if resp.status_code == 200:
                versions = resp.json()
                seen = set()
                for v in versions:
                    parts = v.split(".")
                    if len(parts) >= 2:
                        patch = f"{parts[0]}.{parts[1]}"
                        if patch not in seen:
                            seen.add(patch)
                            patches.append(patch)
                        if len(patches) >= 6:
                            break
    except Exception as e:
        logger.error("Failed to fetch available patches: %s", e)
    return patches


def get_stable_champ_wr(champ_key: str, rank_key: str, current_meta: dict) -> tuple[float, int, str]:
    """
    Resolve the most reliable WR for a champion using a fallback chain:
    1. Current meta data with enough games (>= MIN_GAMES_TRUSTED)
    2. Most recent patch snapshot with data
    3. Current meta data with ANY data (niche fallback)
    4. Ultimate fallback: 50.0
    
    Returns (wr, games, source_label).
    """
    # 1. Check current live meta
    current_champs = current_meta.get("data", {}).get(rank_key, {}).get("champions", {})
    current = current_champs.get(champ_key)
    if current and current.get("games", 0) >= MIN_GAMES_TRUSTED:
        return current["wr"], current["games"], "live"

    # 2. Check patch snapshots (newest first)
    saved = list_saved_patches()
    for patch in saved:
        snap = load_patch_snapshot(patch)
        snap_champs = snap.get("data", {}).get(rank_key, {}).get("champions", {})
        snap_entry = snap_champs.get(champ_key)
        if snap_entry and snap_entry.get("games", 0) >= MIN_GAMES_NICHE:
            return snap_entry["wr"], snap_entry["games"], f"snapshot:{patch}"

    # 3. Niche fallback: use current data even if low games
    if current and current.get("games", 0) > 0:
        return current["wr"], current["games"], "live:niche"

    # 4. Ultimate fallback
    return 50.0, 0, "fallback"
