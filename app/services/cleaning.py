import csv
import io
import logging
import re
from datetime import datetime
from typing import Any

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

DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
)

CURRENCY_PATTERN = re.compile(r"[₹$€£,\s]")


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


def _parse_date(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None

    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue

    return value


def _parse_amount(value: str) -> float | None:
    if not value:
        return None
    cleaned = CURRENCY_PATTERN.sub("", value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def clean_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Apply deterministic cleaning rules and remove exact duplicate rows."""
    cleaned: list[dict[str, Any]] = []

    for row in rows:
        category = row.get("category") or "Uncategorised"
        if not category.strip():
            category = "Uncategorised"

        record: dict[str, Any] = {
            "txn_id": row.get("txn_id") or None,
            "date": _parse_date(row.get("date", "")),
            "merchant": row.get("merchant") or None,
            "amount": _parse_amount(row.get("amount", "")),
            "currency": (row.get("currency") or "").upper() or None,
            "status": (row.get("status") or "").upper() or None,
            "category": category,
            "account_id": row.get("account_id") or None,
            "notes": row.get("notes") or None,
            "is_anomaly": False,
            "anomaly_reason": None,
            "llm_category": None,
            "llm_raw_response": None,
            "llm_failed": False,
        }
        cleaned.append(record)

    seen: set[tuple] = set()
    deduped: list[dict[str, Any]] = []
    for record in cleaned:
        key = (
            record["txn_id"],
            record["date"],
            record["merchant"],
            record["amount"],
            record["currency"],
            record["status"],
            record["category"],
            record["account_id"],
            record["notes"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)

    logger.info("Cleaned %d rows down to %d unique rows", len(rows), len(deduped))
    return deduped
