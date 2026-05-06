from fastapi import APIRouter

from app.api.chat import router as chat_router
from app.api.search import router as search_router
from app.api.sources import router as sources_router

router = APIRouter(prefix="/api/v1")
router.include_router(sources_router)
router.include_router(search_router)
router.include_router(chat_router)


@router.get("/ping")
async def ping():
    return {"pong": True}
