import csv
import io
import logging

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = frozenset({
    "txn_id",
    "date",
    "merchant",
    "amount",
    "currency",
    "status",
    "category",
    "account_id",
})


def validate_csv_content(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Validate CSV structure and return headers plus raw rows."""
    if not content.strip():
        raise ValueError("Uploaded file is empty")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV header row is missing")

    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, str]] = []
    for row in reader:
        normalized = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if not any(normalized.values()):
            continue
        rows.append(normalized)

    if not rows:
        raise ValueError("CSV contains no data rows")

    logger.info("Validated CSV with %d data rows", len(rows))
    return headers, rows
