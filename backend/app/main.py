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
from .state import ALLOWED_ORIGINS
from .services import win_predictor
from .services.db import init_db
from .services import ingestion
from .services import meta_scraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _meta_scheduler():
    """Tierlist refresh every 4 h; full deep sync daily at 5:30 AM server time."""
    await asyncio.sleep(30)  # let uvicorn finish startup

    # If meta data is missing or stale, do an immediate tierlist sync
    meta = meta_scraper.get_meta_data()
    last_tierlist_ts = meta.get("updated_at", 0)
    if time.time() - last_tierlist_ts > 4 * 3600:
        logger.info("Scheduler: stale meta on startup — triggering tierlist sync")
        asyncio.create_task(meta_scraper.sync_meta(mode="tierlist"))
        last_tierlist_ts = time.time()

    last_full_date = None

    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        now_ts = time.time()
        today = now.date()

        # 1. Full Deep Sync Priority (5:30 AM Window)
        is_sync_window = (now.hour == 5 and now.minute >= 30)
        
        if is_sync_window and last_full_date != today:
            if not meta_scraper.is_sync_active():
                last_full_date = today
                logger.info("Scheduler: starting daily matchup sync (5:30 AM window)")
                asyncio.create_task(meta_scraper.sync_meta(mode="matchups"))
                continue  # Skip tierlist check during this trigger minute

        # 2. Regular Tierlist Refresh (every 4 hours)
        # Skip if in the deep sync window or if any sync is already active
        elif not is_sync_window and not meta_scraper.is_sync_active():
            if now_ts - last_tierlist_ts >= 4 * 3600:
                last_tierlist_ts = now_ts
                logger.info("Scheduler: starting 4-hour tierlist refresh")
                asyncio.create_task(meta_scraper.sync_meta(mode="tierlist"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    win_predictor.load_or_train_model()
    await meta_scraper._ensure_champ_ids()
    worker_task = asyncio.create_task(ingestion.ingestion_worker())
    scheduler_task = asyncio.create_task(_meta_scheduler())
    yield
    worker_task.cancel()
    scheduler_task.cancel()
    for t in (worker_task, scheduler_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="League Coach API", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("422 on %s %s — errors: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

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
    return {"status": "ok", "app": "Rift IQ Backend"}
