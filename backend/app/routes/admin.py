import asyncio
import sqlite3

from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from ..state import DB_PATH, ADMIN_API_KEY
from ..services import db, win_predictor
from ..services.meta_scraper import get_meta_data, _CHAMP_ID_MAP, is_sync_active, is_sync_paused, get_sync_mode, sync_meta, cancel_sync, toggle_pause

router = APIRouter(tags=["Admin & Ingestion"])

api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)

async def verify_admin(api_key: str = Security(api_key_header)):
    if not api_key or not ADMIN_API_KEY or api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )

@router.get("/ingest/status", dependencies=[Depends(verify_admin)])
async def ingest_status():
    from ..state import is_rate_limited, get_rate_limit_remaining
    status = await db.get_ingestion_status()
    status["rate_limited"] = is_rate_limited()
    status["rate_limit_remaining"] = get_rate_limit_remaining()
    return status

@router.post("/ingest/toggle", dependencies=[Depends(verify_admin)])
async def ingest_toggle():
    return await db.toggle_ingestion()

@router.post("/admin/retrain", dependencies=[Depends(verify_admin)])
async def admin_retrain():
    return win_predictor.retrain_on_real_data()

@router.get("/admin/data-summary", dependencies=[Depends(verify_admin)])
async def admin_data_summary():
    from ..services.meta_scraper import _ensure_champ_ids
    await _ensure_champ_ids()
    ingest = await db.get_ingestion_status()
    meta = get_meta_data()
    
    champ_names = {str(v): k.capitalize() for k, v in _CHAMP_ID_MAP.items()}

    match_count = 0
    try:
        with sqlite3.connect(DB_PATH) as conn:
            match_count = conn.execute("SELECT COUNT(*) FROM training_matches").fetchone()[0]
    except Exception:
        pass

    ranks_data = meta.get("data", {})
    total_champs = 0
    if ranks_data:
        all_cids = set()
        for r_data in ranks_data.values():
            all_cids.update(r_data.get("champions", {}).keys())
        total_champs = len(all_cids)
    
    return {
        "ingestion": ingest,
        "champ_names": champ_names,
        "meta": {
            "updated_at": meta.get("updated_at"),
            "ranks": list(ranks_data.keys()),
            "champion_count": total_champs,
            "details": ranks_data,
            "active": is_sync_active(),
            "paused": is_sync_paused(),
            "mode": get_sync_mode()
        },
        "training": {
            "match_count": match_count
        }
    }

@router.post("/admin/sync-meta", dependencies=[Depends(verify_admin)])
async def admin_sync_meta(mode: str = "full"):
    asyncio.create_task(sync_meta(mode))
    return {"ok": True, "message": f"Meta sync ({mode}) started in background"}

@router.post("/admin/cancel-sync", dependencies=[Depends(verify_admin)])
async def admin_cancel_sync():
    success = cancel_sync()
    return {"ok": success, "message": "Cancel requested" if success else "No active sync"}

@router.get("/admin/sync-status", dependencies=[Depends(verify_admin)])
async def admin_sync_status():
    return {
        "active": is_sync_active(),
        "paused": is_sync_paused()
    }

@router.post("/admin/toggle-sync-pause", dependencies=[Depends(verify_admin)])
async def admin_toggle_sync_pause():
    new_state = toggle_pause()
    return {"ok": True, "paused": new_state}

@router.post("/admin/cleanup", dependencies=[Depends(verify_admin)])
async def admin_cleanup():
    from ..services.db import cleanup_stale_data
    counts = cleanup_stale_data()
    return {"ok": True, "counts": counts}
