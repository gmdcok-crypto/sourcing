"""Admin CID 키워드 소싱용 검색량·CTR 점수 (선형 보간 / 구간 plateau)."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

# (월검색량, 점수) — 3만 피크, 10만 이상 메가 키워드 감점
SEARCH_VOLUME_SCORE_ANCHORS: Sequence[Tuple[int, float]] = (
    (100, 40.0),
    (500, 60.0),
    (3_000, 75.0),
    (10_000, 80.0),
    (20_000, 70.0),
    (30_000, 100.0),
    (100_000, 70.0),
)

# CTR (%) 상한 — plateau (해당 구간이면 고정 점수)
CTR_SCORE_BANDS: Sequence[Tuple[float, float]] = (
    (1.0, 30.0),
    (1.5, 40.0),
    (3.0, 60.0),
    (5.0, 80.0),
)


def _piecewise_linear(
    value: float,
    anchors: Sequence[Tuple[float, float]],
) -> float:
    if not anchors:
        return 0.0
    if value <= anchors[0][0]:
        return float(anchors[0][1])
    if value >= anchors[-1][0]:
        return float(anchors[-1][1])
    for index in range(len(anchors) - 1):
        x0, y0 = anchors[index]
        x1, y1 = anchors[index + 1]
        if x0 <= value <= x1:
            if x1 == x0:
                return float(y0)
            ratio = (value - x0) / (x1 - x0)
            return float(y0 + ratio * (y1 - y0))
    return float(anchors[-1][1])


def score_monthly_search_volume(monthly_searches: Optional[int]) -> Optional[float]:
    """월검색량 → 검색량 점수 (0~100 스케일, 앵커 간 선형 보간)."""
    if monthly_searches is None:
        return None
    volume = max(0, int(monthly_searches))
    raw = _piecewise_linear(float(volume), SEARCH_VOLUME_SCORE_ANCHORS)
    return round(raw, 2)


def score_ctr_bands(ctr_pct: Optional[float]) -> Optional[float]:
    """CTR(%) → CTR 점수 (구간 plateau). >5.0% → 100."""
    if ctr_pct is None:
        return None
    ctr = max(0.0, float(ctr_pct))
    for upper_bound, band_score in CTR_SCORE_BANDS:
        if ctr <= upper_bound:
            return band_score
    return 100.0


def score_keyword_final(
    search_volume_score: Optional[float],
    ctr_score: Optional[float],
) -> Optional[float]:
    """최종 점수 = (검색량 점수 + CTR 점수) / 2."""
    if search_volume_score is None or ctr_score is None:
        return None
    return round((float(search_volume_score) + float(ctr_score)) / 2, 2)


def format_score_display(score: Optional[float]) -> str:
    if score is None:
        return "-"
    rounded = round(float(score), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}"
