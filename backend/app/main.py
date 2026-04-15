import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import api
from .state import ALLOWED_ORIGINS
from .services import win_predictor
from .services.db import init_db
from .services import ingestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    win_predictor.load_or_train_model()
    worker_task = asyncio.create_task(ingestion.ingestion_worker())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="League Coach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

app.include_router(api.router)

@app.get("/")
async def health_check():
    return {"status": "healthy"}
