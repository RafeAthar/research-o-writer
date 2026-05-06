from fastapi import APIRouter

from app.api.sources import router as sources_router

router = APIRouter(prefix="/api/v1")
router.include_router(sources_router)


@router.get("/ping")
async def ping():
    return {"pong": True}
