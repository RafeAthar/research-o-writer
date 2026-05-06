from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")


@router.get("/ping")
async def ping():
    return {"pong": True}
