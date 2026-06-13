import json
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset({
    "Food",
    "Shopping",
    "Travel",
    "Transport",
    "Utilities",
    "Cash Withdrawal",
    "Entertainment",
    "Other",
})


class OllamaClient:
    """Thin client for the local Ollama generate API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.max_retries = settings.llm_max_retries
        self.retry_base_delay = settings.llm_retry_base_delay

    def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("response", "").strip()
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = self.retry_base_delay ** attempt
                    logger.warning(
                        "Ollama call failed (attempt %d/%d): %s — retrying in %.1fs",
                        attempt,
                        self.max_retries,
                        exc,
                        delay,
                    )
                    time.sleep(delay)

        raise RuntimeError(f"Ollama request failed after {self.max_retries} retries: {last_error}") from last_error


def extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from an LLM response, tolerating surrounding text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def classify_transactions_batch(
    client: OllamaClient,
    transactions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """Classify a batch of uncategorised transactions via LLM."""
    items = [
        {
            "index": idx,
            "merchant": txn.get("merchant"),
            "amount": txn.get("amount"),
            "currency": txn.get("currency"),
            "notes": txn.get("notes"),
        }
        for idx, txn in enumerate(transactions)
    ]

    prompt = (
        "Classify each transaction into exactly one category from this list: "
        "Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other.\n"
        "Return JSON only with shape: "
        '{"classifications": [{"index": 0, "category": "Food"}]}.\n'
        f"Transactions: {json.dumps(items)}"
    )

    raw = client.generate(prompt, json_mode=True)
    parsed = extract_json(raw)
    classifications = parsed.get("classifications", [])

    results: list[dict[str, Any]] = []
    for entry in classifications:
        category = entry.get("category", "Other")
        if category not in VALID_CATEGORIES:
            category = "Other"
        results.append({"index": entry.get("index"), "category": category})

    return results, raw


def generate_narrative_summary(
    client: OllamaClient,
    *,
    total_spend_inr: float,
    total_spend_usd: float,
    top_merchants: list[dict[str, Any]],
    anomaly_count: int,
    category_breakdown: list[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    """Generate a structured narrative summary via a single LLM call."""
    context = {
        "total_spend_inr": total_spend_inr,
        "total_spend_usd": total_spend_usd,
        "top_merchants": top_merchants,
        "anomaly_count": anomaly_count,
        "category_breakdown": category_breakdown,
    }

    prompt = (
        "You are a financial analyst. Based on the transaction aggregates below, "
        "return JSON only with keys: narrative (2-3 sentences), risk_level "
        "(low, medium, or high).\n"
        f"Data: {json.dumps(context)}"
    )

    raw = client.generate(prompt, json_mode=True)
    parsed = extract_json(raw)

    narrative = parsed.get("narrative", "")
    risk_level = str(parsed.get("risk_level", "low")).lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "medium" if anomaly_count > 0 else "low"

    return {"narrative": narrative, "risk_level": risk_level}, raw
