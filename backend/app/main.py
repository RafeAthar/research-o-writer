import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.config import get_settings

logger = logging.getLogger(__name__)


def _warm_models() -> None:
    """Load the local embedder + reranker so the first chat is fast.

    Runs in a worker thread; failures are logged, not fatal (e.g. offline,
    no disk for the HF cache). The first real request will simply retry.
    """
    try:
        from app.services.embedder import get_embedder
        from app.services.reranker import get_reranker

        s = get_settings()
        if s.embedding_provider.strip().lower() == "local":
            logger.info("warming embedder…")
            get_embedder()
        if s.reranker_provider.strip().lower() == "local":
            logger.info("warming reranker…")
            get_reranker()
        logger.info("model warm-up complete")
    except Exception:  # noqa: BLE001 — warm-up must never crash the server
        logger.exception("model warm-up failed; models will load lazily on first use")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().warm_models_on_startup:
        # Don't block startup: load in a background thread while we serve.
        asyncio.create_task(asyncio.to_thread(_warm_models))
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Research-o-Writer API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/healthz", tags=["meta"])
    async def healthz():
        return {"ok": True, "env": settings.app_env}

    return app


app = create_app()
