import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import jobs_router
from app.config import get_settings
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    logger.info("%s API starting", settings.app_name)
    yield
    logger.info("%s API shutting down", settings.app_name)


app = FastAPI(
    title="LedgerLens",
    description="AI-powered transaction processing pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
