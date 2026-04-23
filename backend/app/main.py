import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .routes import api
from .state import ALLOWED_ORIGINS, DATA_DIR
from .services import win_predictor, ingestion, meta_scraper
from .services.db import init_db, get_ingestion_status, resume_ingestion

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def _meta_scheduler():
    """
    Background scheduler for metadata maintenance:
    - Tierlist refresh: Every 4 hours.
    - Deep sync: Daily at 5:30 AM server time.
    - Ingestion: Auto-resume orphans after 30 minutes.
    """
    await asyncio.sleep(10)  # Initial wait for server stabilization

    # Initial boot check: trigger tierlist sync if data is missing or stale
    meta = meta_scraper.get_meta_data()
    last_tierlist_ts = meta.get("updated_at", 0)
    
    if time.time() - last_tierlist_ts > 4 * 3600:
        logger.info("Scheduler: Stale metadata detected on startup. Triggering tierlist sync...")
        asyncio.create_task(meta_scraper.sync_meta(mode="tierlist"))
        last_tierlist_ts = time.time()

    sync_marker_path = DATA_DIR / ".last_full_sync"
    
    def get_last_full_date():
        try:
            return sync_marker_path.read_text().strip()
        except: 
            return None
    
    while True:
        await asyncio.sleep(60)
        now = datetime.utcnow()
        now_ts = time.time()
        today_str = now.strftime("%Y-%m-%d")
        
        # 1. Daily Deep Sync Check (Target: 05:30 AM UTC)
        is_after_trigger_hour = (now.hour > 5 or (now.hour == 5 and now.minute >= 30))
        last_full_date_str = get_last_full_date()
        
        if is_after_trigger_hour and last_full_date_str != today_str:
            if not meta_scraper.is_sync_active():
                logger.info("Scheduler: Starting daily full sync. (Target: 05:30 UTC, Current: %02d:%02d UTC)", now.hour, now.minute)
                asyncio.create_task(meta_scraper.sync_meta(mode="full"))
                continue 

        # 2. Periodic Tierlist Refresh (Every 4 hours)
        elif not meta_scraper.is_sync_active():
            if now_ts - last_tierlist_ts >= 4 * 3600:
                last_tierlist_ts = now_ts
                logger.info("Scheduler: Starting periodic 4-hour tierlist refresh.")
                asyncio.create_task(meta_scraper.sync_meta(mode="tierlist"))

        # 3. Ingestion Safety: Auto-Resume orphaned/paused workers (>30 mins)
        try:
            status = await get_ingestion_status()
            if status.get("is_paused") and status.get("paused_at", 0) > 0:
                if now_ts - status["paused_at"] >= 30 * 60:
                    logger.info("Scheduler: Ingestion worker paused for >30m. Auto-resuming to prevent data gaps.")
                    await resume_ingestion()
        except Exception as e:
            logger.error("Scheduler: Maintenance check encountered an error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for startup and graceful shutdown."""
    init_db()
    win_predictor.load_or_train_model()
    await meta_scraper._ensure_champ_ids()
    
    # Initialize background workers
    worker_task = asyncio.create_task(ingestion.ingestion_worker())
    scheduler_task = asyncio.create_task(_meta_scheduler())
    
    yield
    
    # Graceful shutdown of workers
    logger.info("Application shutting down. Cleaning up background tasks...")
    worker_task.cancel()
    scheduler_task.cancel()
    
    await asyncio.gather(worker_task, scheduler_task, return_exceptions=True)


app = FastAPI(
    title="League Coach API",
    description="Backend services for Rift IQ AI analysis and profile enrichment.",
    lifespan=lifespan
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": "Validation Error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

app.include_router(api.router)

@app.get("/")
async def health_check():
    """Simple health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "Rift IQ Backend",
        "timestamp": datetime.now().isoformat()
    }
