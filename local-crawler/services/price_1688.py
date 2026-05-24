from __future__ import annotations

import re
from statistics import median
from typing import Iterable, List, Optional


_PRICE_PATTERNS = (
    re.compile(r"¥\s*([\d,]+(?:\.\d+)?)"),
    re.compile(r"([\d,]+(?:\.\d+)?)\s*元"),
    re.compile(r'"price"\s*:\s*"?([\d,]+(?:\.\d+)?)"?'),
    re.compile(r'priceAmount\s*[:=]\s*"?([\d,]+(?:\.\d+)?)"?'),
)


def parse_price_cny(text: str) -> Optional[float]:
    raw = str(text or "").strip()
    if not raw:
        return None
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        digits = match.group(1).replace(",", "")
        try:
            value = float(digits)
        except ValueError:
            continue
        if 0 < value < 1_000_000:
            return value
    return None


def extract_prices_from_text_blob(text: str, *, limit: int = 40) -> List[float]:
    prices: List[float] = []
    seen = set()
    for pattern in _PRICE_PATTERNS:
        for match in pattern.finditer(text or ""):
            digits = match.group(1).replace(",", "")
            try:
                value = float(digits)
            except ValueError:
                continue
            if not (0 < value < 1_000_000):
                continue
            key = round(value, 4)
            if key in seen:
                continue
            seen.add(key)
            prices.append(value)
            if len(prices) >= limit:
                return prices
    return prices


def summarize_prices(
    prices: Iterable[float],
    *,
    top_n: int,
    use_median: bool = False,
    min_price: float = 1.0,
) -> Optional[float]:
    cleaned = sorted(float(p) for p in prices if p and p >= min_price)
    if not cleaned:
        return None
    sample = cleaned[: max(1, top_n)]
    if use_median:
        return round(median(sample), 2)
    return round(sum(sample) / len(sample), 2)
