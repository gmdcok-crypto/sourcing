"""STEP1 키워드 노이즈 필터 (vertical_keyword_extraction 참조, 이식 없음)."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_BRAND_NOISE_PATH = _CONFIG_DIR / "brand_noise_exclusion.yaml"

DEFAULT_BRAND_SUBSTRINGS: tuple[str, ...] = (
    "나이키",
    "아디다스",
    "삼성",
    "LG전자",
    "애플",
    "APPLE",
    "정품인증",
    "공식몰",
    "공식 스토어",
)

_EXPLORATION_NOISE_SUBSTRINGS: tuple[str, ...] = (
    "가구거리",
    "거리",
    "시장",
    "매장",
    "오프라인",
    "아울렛",
    "백화점",
    "도매사이트",
    "위탁판매",
    "위탁",
    "쇼핑몰",
    "도매몰",
    "도매",
    "업체",
    "제작",
    "공장",
    "mro",
    "코팅",
    "b2b",
    "사이트",
    "매매",
    "의정부",
    "그누보드",
    "창업",
    "인쇄",
    "맛집",
    "중고",
    "분양",
    "입양",
    "무료분양",
    "무료입양",
    "파양",
    "보호소",
    "업소용",
    "다이소",
    "무인양품",
    "스타벅스",
    "아트박스",
)

_EXPLORATORY_INTENT_SUBSTRINGS: tuple[str, ...] = (
    "후기",
    "리뷰",
    "비교",
    "뜻",
    "추천순",
    "사용법",
    "종류",
)

_INFO_SUFFIX_RE = re.compile(r"(이란|란\?|뜻|방법|사용법|후기|리뷰)$")

_REGION_TOKENS: tuple[str, ...] = (
    "서울",
    "경기",
    "인천",
    "부산",
    "대구",
    "광주",
    "대전",
    "울산",
    "세종",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
    "학성동",
    "의정부",
)

_CATEGORY_TOKENS: tuple[str, ...] = (
    "주방용품",
    "생활용품",
    "가구",
    "패션",
    "잡화",
    "가전",
    "식기",
    "도시락",
    "텀블러",
    "건조대",
)

_MODEL_CODE_RE = re.compile(r"[A-Z]{2,}\d+|\d+[A-Z]{2,}")


@lru_cache(maxsize=1)
def _load_brand_noise_cfg() -> dict:
    cfg: dict = {
        "exact_brands": [],
        "device_series": [],
        "brand_fragments": list(DEFAULT_BRAND_SUBSTRINGS),
        "character_ip": [],
    }
    if _BRAND_NOISE_PATH.is_file():
        try:
            raw = yaml.safe_load(_BRAND_NOISE_PATH.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                for key in cfg:
                    if isinstance(raw.get(key), list):
                        cfg[key] = [str(x).strip() for x in raw[key] if str(x).strip()]
        except Exception:
            pass
    return cfg


def _norm_frag(text: str) -> str:
    return normalize_keyword(text)


@lru_cache(maxsize=1)
def _exact_brand_norm_set() -> frozenset[str]:
    cfg = _load_brand_noise_cfg()
    return frozenset(_norm_frag(x) for x in cfg.get("exact_brands") or [] if x)


@lru_cache(maxsize=1)
def _substring_fragments_norm() -> tuple[str, ...]:
    cfg = _load_brand_noise_cfg()
    parts: List[str] = []
    for key in ("device_series", "brand_fragments", "character_ip"):
        for x in cfg.get(key) or []:
            n = _norm_frag(str(x))
            if n and n not in parts:
                parts.append(n)
    for x in DEFAULT_BRAND_SUBSTRINGS:
        n = _norm_frag(x)
        if n and n not in parts:
            parts.append(n)
    for x in ("삼성", "애플", "apple"):
        n = _norm_frag(x)
        if n and n not in parts:
            parts.append(n)
    return tuple(parts)


def clear_brand_noise_cache() -> None:
    _load_brand_noise_cfg.cache_clear()
    _exact_brand_norm_set.cache_clear()
    _substring_fragments_norm.cache_clear()


def normalize_keyword(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    cleaned = "".join(
        char
        for char in normalized
        if unicodedata.category(char) not in {"Cc", "Cf", "Cs", "Co", "Cn"}
    )
    return "".join(cleaned.split()).lower()


def is_step1_noise(keyword: str) -> bool:
    """
    STEP1 통합 노이즈: 브랜드(YAML) + B2B/지역 + 정보성·탐색성 + 모델코드.
    데이터랩 CID fetch 직후·merge 후 safety net 공통.
    """
    k_raw = str(keyword or "").strip().replace(" ", "")
    if not k_raw:
        return True
    k = normalize_keyword(k_raw)

    if k in _exact_brand_norm_set():
        return True

    for frag in _substring_fragments_norm():
        if frag in k:
            return True

    if any(tok in k for tok in _EXPLORATION_NOISE_SUBSTRINGS):
        return True

    if any(tok in k for tok in _EXPLORATORY_INTENT_SUBSTRINGS):
        return True

    if _INFO_SUFFIX_RE.search(k_raw):
        return True

    if any(tok in k for tok in _REGION_TOKENS):
        if any(tok in k for tok in _CATEGORY_TOKENS):
            return True

    if _MODEL_CODE_RE.search(k_raw):
        return True

    if any(tok in k for tok in _CATEGORY_TOKENS) and ("b2b" in k or "업소용" in k):
        return True

    if len(k_raw) >= 3 and (k_raw.endswith("동") or k_raw.endswith("역") or k_raw.endswith("점")):
        return True

    return False


def is_noise_keyword(keyword: str) -> bool:
    """admin 키워드 소싱 호환 alias."""
    return is_step1_noise(keyword)


def filter_noise(keywords: List[str]) -> Tuple[List[str], List[str]]:
    valid_list: List[str] = []
    noise_list: List[str] = []

    for keyword in keywords:
        if is_step1_noise(keyword):
            noise_list.append(keyword)
        else:
            valid_list.append(keyword)

    return valid_list, noise_list


def filter_keyword_list_step1_noise(keywords: Iterable[str]) -> Tuple[List[str], int]:
    kept: List[str] = []
    removed = 0
    for kw in keywords:
        text = str(kw or "").strip()
        if not text:
            removed += 1
            continue
        if is_step1_noise(text):
            removed += 1
            continue
        kept.append(text)
    return kept, removed


def apply_step1_noise_flags(rows: List[Dict[str, Any]]) -> int:
    """merge 후 safety net — is_step1_noise 재적용."""
    removed = 0
    for row in rows:
        keyword = str(row.get("keyword") or "").strip()
        if not is_step1_noise(keyword):
            continue
        row["is_noise"] = True
        row["is_valid"] = False
        removed += 1
    return removed
