from __future__ import annotations

import re
from typing import List, Tuple

_NOISE_SUBSTRINGS = (
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
)

_REGION_TOKENS = (
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

_CATEGORY_TOKENS = (
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


def is_noise_keyword(keyword: str) -> bool:
    k_raw = str(keyword or "").strip().replace(" ", "")
    if not k_raw:
        return True

    k = k_raw.lower()

    if any(token.lower() in k for token in _NOISE_SUBSTRINGS):
        return True

    if any(region.lower() in k for region in _REGION_TOKENS):
        if any(category.lower() in k for category in _CATEGORY_TOKENS):
            return True

    if re.search(r"[A-Z]{2,}\d+|\d+[A-Z]{2,}", k_raw):
        return True

    if any(category.lower() in k for category in _CATEGORY_TOKENS) and ("b2b" in k or "업소용" in k):
        return True

    if len(k_raw) >= 3 and (k_raw.endswith("동") or k_raw.endswith("역") or k_raw.endswith("점")):
        return True

    return False


def filter_noise(keywords: List[str]) -> Tuple[List[str], List[str]]:
    valid_list: List[str] = []
    noise_list: List[str] = []

    for keyword in keywords:
        if is_noise_keyword(keyword):
            noise_list.append(keyword)
        else:
            valid_list.append(keyword)

    return valid_list, noise_list
