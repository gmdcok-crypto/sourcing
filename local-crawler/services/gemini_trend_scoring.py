"""Gemini + Google Search 기반 트렌드 마켓 스코어 (0~100)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "gemini_trend_scoring.yaml"

DEFAULT_CONFIG: Dict[str, Any] = {
    "model": "gemini-2.5-flash",
    "temperature": 0.1,
    "reference_month": "2026년 5월",
    "weights": {"velocity": 0.30, "viral": 0.30, "conversion": 0.20, "seasonality": 0.20},
    "tiers": [
        {"min_score": 85, "label": "GOLD"},
        {"min_score": 70, "label": "SILVER"},
        {"min_score": 55, "label": "BRONZE"},
        {"min_score": 0, "label": "WATCH"},
    ],
}


def load_trend_config(path: Optional[Path] = None) -> Dict[str, Any]:
    config_path = path or CONFIG_PATH
    if config_path.is_file() and yaml is not None:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            merged = dict(DEFAULT_CONFIG)
            merged.update(loaded)
            return merged
    return dict(DEFAULT_CONFIG)


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = str(text or "").strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    try:
        payload = json.loads(cleaned)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("gemini_response_not_json")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("gemini_response_not_object")
    return payload


def _clamp_score(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, numeric))


def _normalize_breakdown(raw: Any) -> Dict[str, float]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "velocity": _clamp_score(source.get("velocity")),
        "viral": _clamp_score(source.get("viral")),
        "conversion": _clamp_score(source.get("conversion")),
        "seasonality": _clamp_score(source.get("seasonality")),
    }


def compute_weighted_total(breakdown: Dict[str, float], config: Dict[str, Any]) -> float:
    weights = config.get("weights") or {}
    total = 0.0
    for key, weight in weights.items():
        total += breakdown.get(key, 0.0) * float(weight)
    return round(max(0.0, min(100.0, total)), 1)


def score_to_tier(total_score: float, config: Dict[str, Any]) -> str:
    tiers = sorted(
        list(config.get("tiers") or []),
        key=lambda row: float(row.get("min_score") or 0),
        reverse=True,
    )
    for row in tiers:
        if total_score >= float(row.get("min_score") or 0):
            return str(row.get("label") or "WATCH")
    return "WATCH"


def normalize_trend_payload(keyword: str, raw: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    breakdown = _normalize_breakdown(raw.get("breakdown"))
    model_total = _clamp_score(raw.get("total_score"))
    weighted_total = compute_weighted_total(breakdown, config)
    total_score = weighted_total if breakdown else model_total
    tier = str(raw.get("tier") or "").strip().upper() or score_to_tier(total_score, config)

    return {
        "keyword": str(raw.get("keyword") or keyword).strip(),
        "ai_score": total_score,
        "ai_tier": tier,
        "ai_breakdown": breakdown,
        "ai_brief_reason": str(raw.get("brief_reason") or "").strip(),
        "ai_model_total": model_total,
        "ai_scoring_ready": True,
        "ai_scoring_error": "",
    }


def build_error_payload(keyword: str, message: str) -> Dict[str, Any]:
    return {
        "keyword": keyword,
        "ai_score": None,
        "ai_tier": "ERROR",
        "ai_breakdown": {},
        "ai_brief_reason": message,
        "ai_model_total": None,
        "ai_scoring_ready": False,
        "ai_scoring_error": message,
    }


def _build_prompt(keyword: str, config: Dict[str, Any]) -> str:
    now = datetime.now(timezone.utc).astimezone()
    reference = str(config.get("reference_month") or now.strftime("%Y년 %m월"))
    return f"""
현재 시점은 {reference} (조사 기준일: {now.strftime("%Y-%m-%d")})입니다.
키워드 '{keyword}'에 대해 실시간 Google 검색 및 대한민국 SNS(릴스/틱톡/쇼츠) 트렌드를 조사하세요.

아래 4개 지표를 각각 0~100점으로 채점하세요.
1. velocity (검색량 가속도): 최근 2~3주 언급·검색 우상향 여부
2. viral (숏폼 바이럴): 챌린지·공구·숏폼 노출 활성도
3. conversion (상업 전환): 쿠팡·스마트스토어 최근 리뷰·구매 신호
4. seasonality (시즌 부합): 현재 계절·시즌과의 적합도

반드시 순수 JSON만 출력하세요. 마크다운 코드블록 금지.
{{
  "keyword": "{keyword}",
  "total_score": 0,
  "breakdown": {{
    "velocity": 0,
    "viral": 0,
    "conversion": 0,
    "seasonality": 0
  }},
  "tier": "WATCH",
  "brief_reason": "한 줄 요약"
}}
""".strip()


class GeminiTrendScoringService:
    def __init__(
        self,
        *,
        api_key: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.config = config or load_trend_config()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def verify_keyword_trend_score(self, keyword: str) -> Dict[str, Any]:
        keyword_text = str(keyword or "").strip()
        if not keyword_text:
            return build_error_payload("", "empty_keyword")
        if not self.is_configured():
            return build_error_payload(
                keyword_text,
                "GEMINI_API_KEY가 설정되지 않았습니다.",
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            return build_error_payload(
                keyword_text,
                "google-genai 패키지가 필요합니다. pip install google-genai",
            )

        client = genai.Client(api_key=self.api_key)
        prompt = _build_prompt(keyword_text, self.config)
        try:
            response = client.models.generate_content(
                model=str(self.config.get("model") or "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=float(self.config.get("temperature") or 0.1),
                ),
            )
            raw_text = str(getattr(response, "text", "") or "").strip()
            if not raw_text:
                return build_error_payload(keyword_text, "empty_gemini_response")
            raw_payload = _extract_json_object(raw_text)
            return normalize_trend_payload(keyword_text, raw_payload, self.config)
        except Exception as exc:  # noqa: BLE001
            return build_error_payload(keyword_text, str(exc))


def verify_keyword_trend_score(
    keyword: str,
    *,
    api_key: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    service = GeminiTrendScoringService(api_key=api_key, config=config)
    return service.verify_keyword_trend_score(keyword)
