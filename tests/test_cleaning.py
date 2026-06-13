import pytest

from app.services.anomaly import detect_anomalies
from app.services.cleaning import CsvValidationError, clean_rows, validate_csv_content

SAMPLE_ROWS = [
    {
        "txn_id": "TXN001",
        "date": "15/01/2024",
        "merchant": "Swiggy",
        "amount": "₹450",
        "currency": "inr",
        "status": "completed",
        "category": "",
        "account_id": "ACC001",
        "notes": "",
    },
    {
        "txn_id": "TXN002",
        "date": "2024-01-16",
        "merchant": "IRCTC",
        "amount": "$150",
        "currency": "USD",
        "status": "pending",
        "category": "Travel",
        "account_id": "ACC002",
        "notes": "",
    },
]


def test_validate_csv_rejects_empty_file() -> None:
    with pytest.raises(CsvValidationError, match="empty"):
        validate_csv_content(b"   ")


def test_validate_csv_reports_missing_columns() -> None:
    content = b"txn_id,date\n1,2024-01-01\n"
    with pytest.raises(CsvValidationError, match="missing required columns"):
        validate_csv_content(content)


def test_validate_csv_accepts_valid_file() -> None:
    content = (
        b"txn_id,date,merchant,amount,currency,status,category,account_id\n"
        b"TXN1,2024-01-01,Shop,100,INR,COMPLETED,Food,ACC1\n"
    )
    _, rows = validate_csv_content(content)
    assert len(rows) == 1


def test_clean_rows_normalizes_dates_amounts_and_status() -> None:
    cleaned = clean_rows(SAMPLE_ROWS)
    assert cleaned[0]["date"] == "2024-01-15"
    assert cleaned[0]["amount"] == 450.0
    assert cleaned[0]["currency"] == "INR"
    assert cleaned[0]["status"] == "COMPLETED"
    assert cleaned[0]["category"] == "Uncategorised"


def test_clean_rows_preserves_raw_input() -> None:
    cleaned = clean_rows(SAMPLE_ROWS)
    assert cleaned[0]["raw_date"] == "15/01/2024"
    assert cleaned[0]["raw_amount"] == "₹450"


def test_clean_rows_removes_exact_duplicates() -> None:
    duplicate = SAMPLE_ROWS[0].copy()
    rows = SAMPLE_ROWS + [duplicate]
    cleaned = clean_rows(rows)
    assert len(cleaned) == 2


def test_clean_rows_handles_missing_values_safely() -> None:
    rows = [
        {
            "txn_id": "",
            "date": "",
            "merchant": "  ",
            "amount": "",
            "currency": "",
            "status": "",
            "category": "",
            "account_id": "",
            "notes": "",
        }
    ]
    cleaned = clean_rows(rows)
    assert cleaned[0]["txn_id"] is None
    assert cleaned[0]["amount"] is None
    assert cleaned[0]["category"] == "Uncategorised"
