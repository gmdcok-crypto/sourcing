"""쿠팡 Top10 크롤 데이터 기반 OEM/사입 시장 진입 가능성 점수."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "coupang_entry_scoring.yaml"

DEFAULT_CONFIG: Dict[str, Any] = {
    "top10_slots": 10,
    "delivery_types": {
        "general": 90,
        "seller_rocket": 60,
        "rocket_growth": 60,
        "rocket": 30,
    },
    "delivery_aliases": {
        "일반배송": "general",
        "판매자배송": "general",
        "로켓배송": "rocket",
        "로켓프레시": "rocket",
        "판매자로켓": "seller_rocket",
        "로켓그로스": "rocket_growth",
    },
    "rocket_delivery_types": ["rocket", "seller_rocket", "rocket_growth"],
    "review_entry": {
        "thresholds": [
            {"min_count": 7, "score": 100, "grade": "진입우선"},
            {"min_count": 6, "score": 80, "grade": "양호"},
            {"min_count": 5, "score": 70, "grade": "보통"},
            {"min_count": 4, "score": 60, "grade": "주의"},
            {"min_count": 0, "score": 40, "grade": "협소"},
        ],
        "review_under_limit": 500,
    },
    "tier": {
        "premium_min_median": 1000,
        "diamond_min_median": 700,
        "gold_min_median": 400,
        "scores": {"raw_gem": 100, "gold": 75, "diamond": 45, "premium": 20},
    },
    "rocket_penalty": {
        "bands": [
            {"max_ratio": 30, "score": 100},
            {"max_ratio": 50, "score": 80},
            {"max_ratio": 70, "score": 60},
            {"max_ratio": 100, "score": 30},
        ],
    },
    "rating_quality": {
        "bands": [
            {"min_avg": 4.7, "score": 100},
            {"min_avg": 4.5, "score": 85},
            {"min_avg": 4.3, "score": 70},
            {"min_avg": 0, "score": 50},
        ],
    },
    "final_weights": {
        "review_score": 0.35,
        "delivery_score": 0.20,
        "tier_score": 0.25,
        "rocket_penalty": 0.15,
        "rating_quality": 0.05,
    },
    "final_grades": [
        {"min_score": 90, "grade": "S"},
        {"min_score": 80, "grade": "A"},
        {"min_score": 70, "grade": "B"},
        {"min_score": 60, "grade": "C"},
        {"min_score": 0, "grade": "D"},
    ],
    "entry_decision": {
        "recommend_min_final": 80,
        "recommend_max_rocket_ratio": 55,
        "recommend_tiers": ["raw_gem", "gold"],
        "selective_min_final": 65,
        "hold_max_final": 65,
        "hold_tiers": ["premium"],
        "hold_min_rocket_ratio": 70,
    },
}


@dataclass(frozen=True)
class NormalizedProduct:
    rank: int
    title: str
    price: Optional[float]
    review_count: Optional[int]
    rating: Optional[float]
    delivery_type: str


@dataclass
class ScoringConfig:
    raw: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CONFIG))

    @property
    def top10_slots(self) -> int:
        return int(self.raw.get("top10_slots") or 10)

    @property
    def delivery_types(self) -> Dict[str, float]:
        return {str(k): float(v) for k, v in (self.raw.get("delivery_types") or {}).items()}

    @property
    def delivery_aliases(self) -> Dict[str, str]:
        return {str(k): str(v) for k, v in (self.raw.get("delivery_aliases") or {}).items()}

    @property
    def rocket_delivery_types(self) -> Tuple[str, ...]:
        values = self.raw.get("rocket_delivery_types") or []
        return tuple(str(item) for item in values)

    @property
    def review_under_limit(self) -> int:
        return int((self.raw.get("review_entry") or {}).get("review_under_limit") or 500)

    @property
    def review_thresholds(self) -> List[Dict[str, Any]]:
        return list((self.raw.get("review_entry") or {}).get("thresholds") or [])

    @property
    def tier_cfg(self) -> Dict[str, Any]:
        return dict(self.raw.get("tier") or {})

    @property
    def rocket_penalty_bands(self) -> List[Dict[str, Any]]:
        return list((self.raw.get("rocket_penalty") or {}).get("bands") or [])

    @property
    def rating_quality_bands(self) -> List[Dict[str, Any]]:
        return list((self.raw.get("rating_quality") or {}).get("bands") or [])

    @property
    def final_weights(self) -> Dict[str, float]:
        return {str(k): float(v) for k, v in (self.raw.get("final_weights") or {}).items()}

    @property
    def final_grades(self) -> List[Dict[str, Any]]:
        return list(self.raw.get("final_grades") or [])

    @property
    def entry_decision_cfg(self) -> Dict[str, Any]:
        return dict(self.raw.get("entry_decision") or {})


def load_scoring_config(path: Optional[Path] = None) -> ScoringConfig:
    config_path = path or CONFIG_PATH
    if config_path.is_file() and yaml is not None:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            merged = dict(DEFAULT_CONFIG)
            merged.update(loaded)
            return ScoringConfig(raw=merged)
    return ScoringConfig(raw=dict(DEFAULT_CONFIG))


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _to_int(value: Any) -> Optional[int]:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def normalize_delivery_type(raw: Any, config: ScoringConfig) -> str:
    text = str(raw or "").strip()
    if not text:
        return "general"
    if text in config.delivery_types:
        return text
    alias = config.delivery_aliases.get(text)
    if alias:
        return alias
    lowered = text.lower().replace(" ", "_")
    if lowered in config.delivery_types:
        return lowered
    return "general"


def normalize_top10_products(
    items: Sequence[Mapping[str, Any]],
    *,
    config: Optional[ScoringConfig] = None,
) -> List[NormalizedProduct]:
    cfg = config or load_scoring_config()
    ranked: List[Tuple[int, Mapping[str, Any]]] = []
    for index, item in enumerate(items):
        rank = _to_int(item.get("rank"))
        if rank is None:
            rank = index + 1
        ranked.append((rank, item))
    ranked.sort(key=lambda pair: pair[0])

    normalized: List[NormalizedProduct] = []
    seen_ranks: set[int] = set()
    for rank, item in ranked:
        if rank in seen_ranks:
            continue
        seen_ranks.add(rank)
        rating = _to_float(item.get("rating"))
        if rating is None:
            rating = _to_float(item.get("review_score"))
        normalized.append(
            NormalizedProduct(
                rank=rank,
                title=str(item.get("title") or "").strip(),
                price=_to_float(item.get("price")),
                review_count=_to_int(item.get("review_count")),
                rating=rating,
                delivery_type=normalize_delivery_type(item.get("delivery_type"), cfg),
            )
        )
        if len(normalized) >= cfg.top10_slots:
            break
    return normalized


def calc_review_entry_score(
    products: Sequence[NormalizedProduct],
    config: ScoringConfig,
) -> Tuple[int, float, str]:
    limit = config.review_under_limit
    under_count = sum(
        1
        for product in products
        if product.review_count is not None and product.review_count <= limit
    )
    thresholds = sorted(
        config.review_thresholds,
        key=lambda row: int(row.get("min_count") or 0),
        reverse=True,
    )
    for row in thresholds:
        min_count = int(row.get("min_count") or 0)
        if under_count >= min_count:
            return under_count, float(row.get("score") or 0), str(row.get("grade") or "")
    return under_count, 40.0, "협소"


def calc_delivery_score(products: Sequence[NormalizedProduct], config: ScoringConfig) -> float:
    delivery_map = config.delivery_types
    slots = config.top10_slots
    total = 0.0
    for index in range(slots):
        if index < len(products):
            delivery_key = products[index].delivery_type
            total += float(delivery_map.get(delivery_key, delivery_map.get("general", 90)))
        else:
            total += float(delivery_map.get("general", 90))
    return round(total / max(slots, 1), 2)


def calc_review_median(products: Sequence[NormalizedProduct]) -> Optional[float]:
    values = [float(product.review_count) for product in products if product.review_count is not None]
    if not values:
        return None
    return float(median(values))


def classify_keyword_tier(review_median: Optional[float], config: ScoringConfig) -> str:
    if review_median is None:
        return "raw_gem"
    tier_cfg = config.tier_cfg
    if review_median >= float(tier_cfg.get("premium_min_median") or 1000):
        return "premium"
    if review_median >= float(tier_cfg.get("diamond_min_median") or 700):
        return "diamond"
    if review_median >= float(tier_cfg.get("gold_min_median") or 400):
        return "gold"
    return "raw_gem"


def tier_to_score(keyword_tier: str, config: ScoringConfig) -> float:
    scores = config.tier_cfg.get("scores") or {}
    return float(scores.get(keyword_tier) or scores.get("raw_gem") or 0)


def calc_rocket_ratio(products: Sequence[NormalizedProduct], config: ScoringConfig) -> float:
    slots = config.top10_slots
    rocket_types = set(config.rocket_delivery_types)
    rocket_count = sum(1 for product in products if product.delivery_type in rocket_types)
    return round((rocket_count / max(slots, 1)) * 100, 2)


def calc_rocket_penalty_score(rocket_ratio: float, config: ScoringConfig) -> float:
    bands = sorted(config.rocket_penalty_bands, key=lambda row: float(row.get("max_ratio") or 0))
    for row in bands:
        if rocket_ratio <= float(row.get("max_ratio") or 0):
            return float(row.get("score") or 0)
    return float(bands[-1]["score"]) if bands else 30.0


def calc_avg_rating(products: Sequence[NormalizedProduct]) -> Optional[float]:
    values = [product.rating for product in products if product.rating is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def calc_rating_quality_score(avg_rating: Optional[float], config: ScoringConfig) -> float:
    if avg_rating is None:
        return 50.0
    bands = sorted(config.rating_quality_bands, key=lambda row: float(row.get("min_avg") or 0), reverse=True)
    for row in bands:
        if avg_rating >= float(row.get("min_avg") or 0):
            return float(row.get("score") or 0)
    return 50.0


def calc_final_score(
    *,
    review_score: float,
    delivery_score: float,
    tier_score: float,
    rocket_penalty_score: float,
    rating_quality_score: float,
    config: ScoringConfig,
) -> float:
    weights = config.final_weights
    raw = (
        review_score * weights.get("review_score", 0.35)
        + delivery_score * weights.get("delivery_score", 0.20)
        + tier_score * weights.get("tier_score", 0.25)
        + rocket_penalty_score * weights.get("rocket_penalty", 0.15)
        + rating_quality_score * weights.get("rating_quality", 0.05)
    )
    return round(max(0.0, min(100.0, raw)), 1)


def final_score_to_grade(final_score: float, config: ScoringConfig) -> str:
    bands = sorted(config.final_grades, key=lambda row: float(row.get("min_score") or 0), reverse=True)
    for row in bands:
        if final_score >= float(row.get("min_score") or 0):
            return str(row.get("grade") or "D")
    return "D"


def decide_entry(
    *,
    final_score: float,
    rocket_ratio: float,
    keyword_tier: str,
    config: ScoringConfig,
) -> str:
    rules = config.entry_decision_cfg
    hold_tiers = set(rules.get("hold_tiers") or [])
    recommend_tiers = set(rules.get("recommend_tiers") or [])

    if (
        final_score >= float(rules.get("recommend_min_final") or 80)
        and rocket_ratio <= float(rules.get("recommend_max_rocket_ratio") or 55)
        and keyword_tier in recommend_tiers
    ):
        return "recommend"

    if (
        final_score < float(rules.get("hold_max_final") or 65)
        or keyword_tier in hold_tiers
        or rocket_ratio >= float(rules.get("hold_min_rocket_ratio") or 70)
    ):
        return "hold"

    if final_score >= float(rules.get("selective_min_final") or 65):
        return "selective"

    return "hold"


class CoupangEntryScoringEngine:
    """쿠팡 Top10 → 시장 진입 가능성 점수."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config = load_scoring_config(config_path)

    def score_keyword(
        self,
        keyword: str,
        top10_items: Sequence[Mapping[str, Any]],
        *,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        products = normalize_top10_products(top10_items, config=self.config)
        meta = dict(metadata or {})
        slots = self.config.top10_slots

        if not products:
            return self._empty_result(keyword=keyword, metadata=meta, reason="no_top10_items")

        review_under_500_count, coupang_review_score, coupang_review_grade = calc_review_entry_score(
            products, self.config
        )
        coupang_delivery_score = calc_delivery_score(products, self.config)
        review_median_value = calc_review_median(products)
        keyword_tier = classify_keyword_tier(review_median_value, self.config)
        tier_score = tier_to_score(keyword_tier, self.config)
        rocket_ratio = calc_rocket_ratio(products, self.config)
        rocket_penalty_score = calc_rocket_penalty_score(rocket_ratio, self.config)
        avg_rating = calc_avg_rating(products)
        rating_quality_score = calc_rating_quality_score(avg_rating, self.config)

        final_score = calc_final_score(
            review_score=coupang_review_score,
            delivery_score=coupang_delivery_score,
            tier_score=tier_score,
            rocket_penalty_score=rocket_penalty_score,
            rating_quality_score=rating_quality_score,
            config=self.config,
        )
        final_grade = final_score_to_grade(final_score, self.config)
        entry_decision = decide_entry(
            final_score=final_score,
            rocket_ratio=rocket_ratio,
            keyword_tier=keyword_tier,
            config=self.config,
        )

        review_distribution = [
            {
                "rank": product.rank,
                "review_count": product.review_count,
                "under_500": (
                    product.review_count is not None
                    and product.review_count <= self.config.review_under_limit
                ),
            }
            for product in products
        ]

        return {
            "keyword": keyword,
            "group_name": meta.get("group_name") or "",
            "theme_name": meta.get("theme_name") or "",
            "theme_detail": meta.get("theme_detail") or "",
            "top10_count": len(products),
            "top10_incomplete": len(products) < slots,
            "review_under_500_count": review_under_500_count,
            "coupang_review_score": coupang_review_score,
            "coupang_review_grade": coupang_review_grade,
            "coupang_delivery_score": coupang_delivery_score,
            "review_median": review_median_value,
            "keyword_tier": keyword_tier,
            "tier_score": tier_score,
            "rocket_ratio": rocket_ratio,
            "rocket_penalty_score": rocket_penalty_score,
            "avg_rating": avg_rating,
            "rating_quality_score": rating_quality_score,
            "final_score": final_score,
            "final_grade": final_grade,
            "entry_decision": entry_decision,
            "review_distribution": review_distribution,
            "delivery_breakdown": [
                {
                    "rank": product.rank,
                    "delivery_type": product.delivery_type,
                    "delivery_score": self.config.delivery_types.get(
                        product.delivery_type,
                        self.config.delivery_types.get("general", 90),
                    ),
                }
                for product in products
            ],
            "scoring_ready": True,
            "scoring_reason": "",
        }

    def _empty_result(
        self,
        *,
        keyword: str,
        metadata: Mapping[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "keyword": keyword,
            "group_name": metadata.get("group_name") or "",
            "theme_name": metadata.get("theme_name") or "",
            "theme_detail": metadata.get("theme_detail") or "",
            "top10_count": 0,
            "top10_incomplete": True,
            "review_under_500_count": 0,
            "coupang_review_score": 0,
            "coupang_review_grade": "-",
            "coupang_delivery_score": 0,
            "review_median": None,
            "keyword_tier": "raw_gem",
            "tier_score": 0,
            "rocket_ratio": 0,
            "rocket_penalty_score": 0,
            "avg_rating": None,
            "rating_quality_score": 0,
            "final_score": 0,
            "final_grade": "D",
            "entry_decision": "hold",
            "review_distribution": [],
            "delivery_breakdown": [],
            "scoring_ready": False,
            "scoring_reason": reason,
        }
