import logging
from typing import Any

from app.config import get_settings
from app.services.llm import OllamaClient, classify_transactions_batch
from app.utils.job_log import job_logger

logger = logging.getLogger(__name__)

UNCATEGORISED_VALUES = frozenset({
    "",
    "uncategorised",
    "uncategorized",
    "none",
    "null",
    "n/a",
})


def needs_classification(category: str | None) -> bool:
    return (category or "").strip().lower() in UNCATEGORISED_VALUES


def classify_missing_categories(
    rows: list[dict[str, Any]],
    *,
    job_id: int | None = None,
) -> list[dict[str, Any]]:
    """Batch-classify uncategorised rows; mark failed batches without aborting the job."""
    log = job_logger(logger, job_id or "-", "classification")
    settings = get_settings()
    client = OllamaClient()

    pending_indices = [
        i for i, row in enumerate(rows) if needs_classification(row.get("category"))
    ]
    if not pending_indices:
        log.info("no_rows_to_classify")
        return rows

    batch_size = settings.llm_batch_size
    total_batches = (len(pending_indices) + batch_size - 1) // batch_size
    log.info(
        "pending_rows=%d total_batches=%d batch_size=%d",
        len(pending_indices),
        total_batches,
        batch_size,
    )

    for batch_num, start in enumerate(range(0, len(pending_indices), batch_size), start=1):
        batch_indices = pending_indices[start : start + batch_size]
        batch_rows = [rows[i] for i in batch_indices]

        try:
            classifications, raw = classify_transactions_batch(client, batch_rows)
            by_index = {entry["index"]: entry["category"] for entry in classifications}
            for local_idx, global_idx in enumerate(batch_indices):
                category = by_index.get(local_idx, "Other")
                rows[global_idx]["llm_category"] = category
                rows[global_idx]["category"] = category
                rows[global_idx]["llm_raw_response"] = raw
                rows[global_idx]["llm_failed"] = False
            log.info("batch=%d/%d status=success", batch_num, total_batches)
        except Exception as exc:
            log.error("batch=%d/%d status=failed error=%s", batch_num, total_batches, exc)
            for global_idx in batch_indices:
                rows[global_idx]["llm_failed"] = True
                rows[global_idx]["llm_raw_response"] = str(exc)

    return rows
