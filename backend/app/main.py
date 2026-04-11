import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import api
from .state import ALLOWED_ORIGINS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="League Coach API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api.router)

@app.get("/")
async def health_check():
    return {"status": "healthy"}
