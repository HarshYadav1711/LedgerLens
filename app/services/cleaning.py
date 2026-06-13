import csv
import io
import logging
import re
from datetime import datetime
from typing import Any

from app.utils.safe import clean_str, clean_str_default, safe_upper

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


class CsvValidationError(ValueError):
    """Raised when an uploaded CSV fails structural validation."""


def validate_csv_content(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Validate CSV structure and return headers plus raw rows."""
    if not content or not content.strip():
        raise CsvValidationError("Uploaded file is empty")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError(
            "CSV must be UTF-8 encoded; re-save the file as UTF-8 and retry"
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvValidationError("CSV header row is missing")

    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
    if not headers:
        raise CsvValidationError("CSV header row contains no usable column names")

    duplicates = sorted({h for h in headers if headers.count(h) > 1})
    if duplicates:
        raise CsvValidationError(
            f"CSV header row contains duplicate columns: {', '.join(duplicates)}"
        )

    missing = sorted(REQUIRED_COLUMNS - set(headers))
    if missing:
        raise CsvValidationError(
            f"CSV is missing required columns: {', '.join(missing)}. "
            f"Expected: {', '.join(sorted(REQUIRED_COLUMNS))}"
        )

    rows: list[dict[str, str]] = []
    for line_no, row in enumerate(reader, start=2):
        normalized = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if not any(normalized.values()):
            continue
        rows.append(normalized)

    if not rows:
        raise CsvValidationError(
            "CSV contains a header row but no data rows; add at least one transaction"
        )

    logger.info("Validated CSV with %d data rows", len(rows))
    return headers, rows


def _parse_date(value: str) -> str | None:
    value = (value or "").strip()
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
    if not value or not value.strip():
        return None
    cleaned = CURRENCY_PATTERN.sub("", value.strip())
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
        raw_date = clean_str(row.get("date"))
        raw_amount = clean_str(row.get("amount"))
        category = clean_str_default(row.get("category"), "Uncategorised")

        record: dict[str, Any] = {
            "txn_id": clean_str(row.get("txn_id")),
            "date": _parse_date(raw_date or ""),
            "merchant": clean_str(row.get("merchant")),
            "amount": _parse_amount(raw_amount or ""),
            "currency": safe_upper(row.get("currency")),
            "status": safe_upper(row.get("status")),
            "category": category,
            "account_id": clean_str(row.get("account_id")),
            "notes": clean_str(row.get("notes")),
            "raw_date": raw_date,
            "raw_amount": raw_amount,
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
