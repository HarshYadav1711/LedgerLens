import logging
from typing import Any

from app.services.aggregates import (
    compute_anomaly_count,
    compute_category_breakdown,
    compute_top_merchants,
)
from app.services.llm import OllamaClient, generate_narrative_summary

logger = logging.getLogger(__name__)


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
    spend = _spend_totals(rows)
    top_merchants = [m.model_dump() for m in compute_top_merchants(rows)]
    anomaly_count = compute_anomaly_count(rows)
    category_breakdown = [b.model_dump() for b in compute_category_breakdown(rows)]

    aggregates = {
        "total_spend_inr": spend.get("INR", 0.0),
        "total_spend_usd": spend.get("USD", 0.0),
        "top_merchants": top_merchants,
        "anomaly_count": anomaly_count,
    }

    client = OllamaClient()
    narrative_raw: str | None = None

    try:
        narrative_payload, narrative_raw = generate_narrative_summary(
            client,
            total_spend_inr=aggregates["total_spend_inr"],
            total_spend_usd=aggregates["total_spend_usd"],
            top_merchants=top_merchants,
            anomaly_count=anomaly_count,
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


def _spend_totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        amount = row.get("amount")
        if amount is None:
            continue
        currency = (row.get("currency") or "").upper()
        if currency:
            totals[currency] = totals.get(currency, 0.0) + float(amount)
    return {currency: round(total, 2) for currency in sorted(totals)}
