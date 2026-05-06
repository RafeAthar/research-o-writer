from fastapi import APIRouter, Depends

from app.api.chat import router as chat_router
from app.api.highlights import router as highlights_router
from app.api.projects import router as projects_router
from app.api.search import router as search_router
from app.api.sources import router as sources_router
from app.deps import require_auth

router = APIRouter(prefix="/api/v1")
router.include_router(sources_router)
router.include_router(search_router)
router.include_router(chat_router)
router.include_router(highlights_router)
router.include_router(projects_router)


@router.get("/ping")
async def ping():
    return {"pong": True}


@router.get("/me")
async def me(user_id: int = Depends(require_auth)):
    """Confirms the caller's token and returns their user_id."""
    return {"user_id": user_id}
