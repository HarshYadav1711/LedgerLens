import logging
from collections import Counter, defaultdict
from typing import Any

from app.services.llm import OllamaClient, generate_narrative_summary

logger = logging.getLogger(__name__)


def effective_category(row: dict[str, Any]) -> str:
    return row.get("llm_category") or row.get("category") or "Uncategorised"


def build_category_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()

    for row in rows:
        category = effective_category(row)
        counts[category] += 1
        amount = row.get("amount")
        if amount is not None:
            totals[category] += float(amount)

    return [
        {"category": cat, "count": counts[cat], "total_amount": round(totals[cat], 2)}
        for cat in sorted(counts)
    ]


def _compute_aggregates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_inr = 0.0
    total_usd = 0.0
    merchant_totals: dict[str, float] = defaultdict(float)
    anomaly_count = 0

    for row in rows:
        amount = row.get("amount")
        if amount is None:
            continue

        currency = (row.get("currency") or "").upper()
        if currency == "INR":
            total_inr += float(amount)
        elif currency == "USD":
            total_usd += float(amount)

        merchant = row.get("merchant") or "Unknown"
        merchant_totals[merchant] += float(amount)

        if row.get("is_anomaly"):
            anomaly_count += 1

    top_merchants = [
        {"merchant": merchant, "total_amount": round(amount, 2)}
        for merchant, amount in sorted(
            merchant_totals.items(), key=lambda item: item[1], reverse=True
        )[:3]
    ]

    return {
        "total_spend_inr": round(total_inr, 2),
        "total_spend_usd": round(total_usd, 2),
        "top_merchants": top_merchants,
        "anomaly_count": anomaly_count,
    }


def _fallback_narrative(aggregates: dict[str, Any], row_count: int) -> dict[str, str]:
    anomaly_count = aggregates["anomaly_count"]
    return {
        "narrative": (
            f"Processed {row_count} transactions with {anomaly_count} anomalies flagged. "
            f"Total spend: INR {aggregates['total_spend_inr']:.2f}, "
            f"USD {aggregates['total_spend_usd']:.2f}."
        ),
        "risk_level": (
            "high" if anomaly_count >= 3 else ("medium" if anomaly_count else "low")
        ),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregates and generate a best-effort LLM narrative summary."""
    aggregates = _compute_aggregates(rows)
    category_breakdown = build_category_breakdown(rows)

    client = OllamaClient()
    narrative_raw: str | None = None

    try:
        narrative_payload, narrative_raw = generate_narrative_summary(
            client,
            total_spend_inr=aggregates["total_spend_inr"],
            total_spend_usd=aggregates["total_spend_usd"],
            top_merchants=aggregates["top_merchants"],
            anomaly_count=aggregates["anomaly_count"],
            category_breakdown=category_breakdown,
        )
        logger.info("Narrative summary generated via LLM")
    except Exception as exc:
        logger.warning("Narrative generation failed, using deterministic fallback: %s", exc)
        narrative_payload = _fallback_narrative(aggregates, len(rows))
        narrative_raw = str(exc)

    return {
        **aggregates,
        "narrative": narrative_payload["narrative"],
        "risk_level": narrative_payload["risk_level"],
        "narrative_raw": narrative_raw,
        "category_breakdown": category_breakdown,
    }
