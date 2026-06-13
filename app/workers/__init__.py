"""Celery background workers."""

from app.workers import processing  # noqa: F401 — register tasks
