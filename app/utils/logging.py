import logging

from app.config import get_settings


def configure_logging(level: str | None = None) -> None:
    """Configure structured application logging once at process startup."""
    log_level = (level or get_settings().log_level).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
