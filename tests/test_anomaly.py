from app.services.anomaly import detect_anomalies
from app.services.cleaning import clean_rows


def _rows() -> list[dict]:
    raw = [
        {
            "txn_id": "T1",
            "date": "2024-01-01",
            "merchant": "Swiggy",
            "amount": "100",
            "currency": "INR",
            "status": "COMPLETED",
            "category": "Food",
            "account_id": "ACC1",
            "notes": "",
        },
        {
            "txn_id": "T1B",
            "date": "2024-01-01",
            "merchant": "Zomato",
            "amount": "100",
            "currency": "INR",
            "status": "COMPLETED",
            "category": "Food",
            "account_id": "ACC1",
            "notes": "",
        },
        {
            "txn_id": "T2",
            "date": "2024-01-02",
            "merchant": "Swiggy",
            "amount": "1000",
            "currency": "INR",
            "status": "COMPLETED",
            "category": "Food",
            "account_id": "ACC1",
            "notes": "",
        },
        {
            "txn_id": "T3",
            "date": "2024-01-03",
            "merchant": "IRCTC",
            "amount": "50",
            "currency": "USD",
            "status": "COMPLETED",
            "category": "Travel",
            "account_id": "ACC2",
            "notes": "",
        },
    ]
    return clean_rows(raw)


def test_detect_anomalies_flags_high_amount() -> None:
    rows = detect_anomalies(_rows())
    high_value = next(row for row in rows if row["txn_id"] == "T2")
    assert high_value["is_anomaly"] is True
    assert "3x account median" in (high_value["anomaly_reason"] or "")


def test_detect_anomalies_flags_domestic_usd_merchant() -> None:
    rows = detect_anomalies(_rows())
    usd_domestic = next(row for row in rows if row["txn_id"] == "T3")
    assert usd_domestic["is_anomaly"] is True
    assert "domestic-only merchant" in (usd_domestic["anomaly_reason"] or "")


def test_detect_anomalies_leaves_normal_rows_unflagged() -> None:
    rows = detect_anomalies(_rows())
    normal = next(row for row in rows if row["txn_id"] == "T1")
    assert normal["is_anomaly"] is False
    assert normal["anomaly_reason"] is None
