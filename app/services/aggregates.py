"""Deterministic aggregate computations over transaction data."""

from collections import Counter, defaultdict
from typing import Any, Protocol

from app.schemas.transactions import CategoryBreakdownItem, TopMerchantItem


class _TransactionLike(Protocol):
    llm_category: str | None
    category: str | None
    amount: float | None
    currency: str | None
    merchant: str | None
    is_anomaly: bool


def resolve_category(record: _TransactionLike | dict[str, Any]) -> str:
    """Return the effective spending category for a transaction."""
    if isinstance(record, dict):
        return record.get("llm_category") or record.get("category") or "Uncategorised"
    return record.llm_category or record.category or "Uncategorised"


def compute_category_breakdown(
    transactions: list[_TransactionLike | dict[str, Any]],
) -> list[CategoryBreakdownItem]:
    """Compute per-category transaction counts and total spend."""
    totals: dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()

    for txn in transactions:
        category = resolve_category(txn)
        counts[category] += 1
        amount = txn.get("amount") if isinstance(txn, dict) else txn.amount
        if amount is not None:
            totals[category] += float(amount)

    return [
        CategoryBreakdownItem(
            category=category,
            count=counts[category],
            total_amount=round(totals[category], 2),
        )
        for category in sorted(counts)
    ]


def compute_top_merchants(
    transactions: list[_TransactionLike | dict[str, Any]],
    *,
    limit: int = 3,
) -> list[TopMerchantItem]:
    """Rank merchants by total transaction amount (deterministic)."""
    merchant_totals: dict[str, float] = defaultdict(float)

    for txn in transactions:
        amount = txn.get("amount") if isinstance(txn, dict) else txn.amount
        if amount is None:
            continue
        merchant = (
            (txn.get("merchant") if isinstance(txn, dict) else txn.merchant) or "Unknown"
        )
        merchant_totals[merchant] += float(amount)

    ranked = sorted(
        merchant_totals.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        TopMerchantItem(merchant=merchant, total_amount=round(total, 2))
        for merchant, total in ranked[:limit]
    ]


def compute_spend_by_currency(
    transactions: list[_TransactionLike | dict[str, Any]],
) -> dict[str, float]:
    """Sum spend grouped by currency code."""
    totals: dict[str, float] = defaultdict(float)

    for txn in transactions:
        amount = txn.get("amount") if isinstance(txn, dict) else txn.amount
        if amount is None:
            continue
        currency = (
            (txn.get("currency") if isinstance(txn, dict) else txn.currency) or ""
        ).upper()
        if currency:
            totals[currency] += float(amount)

    return {currency: round(total, 2) for currency in sorted(totals)}


def compute_anomaly_count(transactions: list[_TransactionLike | dict[str, Any]]) -> int:
    return sum(
        1
        for txn in transactions
        if (txn.get("is_anomaly") if isinstance(txn, dict) else txn.is_anomaly)
    )
