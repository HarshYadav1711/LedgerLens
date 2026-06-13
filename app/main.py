import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import jobs_router
from app.config import get_settings
from app.schemas.health import HealthResponse
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)

API_VERSION = "0.1.0"


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
    version=API_VERSION,
    lifespan=lifespan,
)

app.include_router(jobs_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name, version=API_VERSION)
