"""Railway 키워드 메타 기반 네이버(검색광고) 최종 점수."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


def _to_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _from_stored(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def compute_naver_final_score(keyword_row: Dict[str, Any]) -> Optional[float]:
    """네이버점수 = (검색량점수 + CTR점수) / 2. 저장값 우선, 없으면 재계산."""
    for key in ("naver_score", "final_score"):
        stored = _from_stored(keyword_row.get(key))
        if stored is not None:
            return stored

    source_payload = keyword_row.get("source_payload")
    if isinstance(source_payload, dict):
        stored = _from_stored(source_payload.get("final_score"))
        if stored is not None:
            return stored
        volume_score = source_payload.get("search_volume_score")
        ctr_score = source_payload.get("ctr_score")
        if volume_score is not None and ctr_score is not None:
            return round((float(volume_score) + float(ctr_score)) / 2, 1)

    searches = _to_int(keyword_row.get("monthly_mobile_searches"))
    ctr = _to_float(keyword_row.get("monthly_mobile_ctr"))
    if searches is None or ctr is None:
        return None

    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from app.services.keyword_scoring import (
            score_ctr_bands,
            score_keyword_final,
            score_monthly_search_volume,
        )

        return score_keyword_final(
            score_monthly_search_volume(searches),
            score_ctr_bands(ctr),
        )
    except Exception:
        return None
