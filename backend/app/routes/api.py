from fastapi import APIRouter

from .player import router as player_router
from .analysis import router as analysis_router
from .live import router as live_router
from .admin import router as admin_router
from .ai import router as ai_router

router = APIRouter(tags=["Main API"])

router.include_router(player_router)
router.include_router(analysis_router)
router.include_router(live_router)
router.include_router(admin_router)
router.include_router(ai_router)
