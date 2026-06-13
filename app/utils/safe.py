"""Safe normalization for missing or blank input values."""


def clean_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def clean_str_default(value: str | None, default: str) -> str:
    return clean_str(value) or default


def safe_upper(value: str | None) -> str | None:
    cleaned = clean_str(value)
    return cleaned.upper() if cleaned else None
