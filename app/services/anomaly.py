import logging
import statistics
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

DOMESTIC_ONLY_BRANDS = frozenset({"swiggy", "ola", "irctc", "zomato", "paytm", "phonepe"})


def _merchant_matches_domestic(merchant: str | None) -> bool:
    if not merchant:
        return False
    normalized = merchant.lower()
    return any(brand in normalized for brand in DOMESTIC_ONLY_BRANDS)


def detect_anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag high-value transactions and domestic merchants billed in USD."""
    by_account: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        account_id = row.get("account_id") or "unknown"
        amount = row.get("amount")
        if amount is not None:
            by_account[account_id].append(float(amount))

    medians: dict[str, float] = {}
    for account_id, amounts in by_account.items():
        if amounts:
            medians[account_id] = statistics.median(amounts)

    flagged = 0
    for row in rows:
        reasons: list[str] = []
        account_id = row.get("account_id") or "unknown"
        amount = row.get("amount")
        currency = (row.get("currency") or "").upper()
        merchant = row.get("merchant")

        if amount is not None and account_id in medians:
            median = medians[account_id]
            if median > 0 and float(amount) > 3 * median:
                reasons.append(
                    f"Amount {amount} exceeds 3x account median ({median:.2f})"
                )

        if currency == "USD" and _merchant_matches_domestic(merchant):
            reasons.append(
                f"USD transaction with domestic-only merchant '{merchant}'"
            )

        row["is_anomaly"] = bool(reasons)
        row["anomaly_reason"] = "; ".join(reasons) if reasons else None
        if reasons:
            flagged += 1

    logger.info("Flagged %d anomalies across %d transactions", flagged, len(rows))
    return rows
