from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any, Dict, List

import httpx


class NaverSearchAdService:
    BASE_URL = "https://api.searchad.naver.com"
    KEYWORDS_TOOL_URI = "/keywordstool"

    def __init__(self, settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.naver_ad_api_key
            and self.settings.naver_ad_secret_key
            and self.settings.naver_ad_customer_id
        )

    async def fetch_keyword_metrics(self, keywords: List[str]) -> Dict[str, Dict[str, Any]]:
        if not self.is_configured or not keywords:
            return {}

        metrics: Dict[str, Dict[str, Any]] = {}
        unique_keywords = []
        seen = set()
        for keyword in keywords:
            key = str(keyword).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique_keywords.append(key)

        async with httpx.AsyncClient(timeout=20.0) as client:
            for batch in self._chunk(unique_keywords, 5):
                headers = self._build_headers(method="GET", uri=self.KEYWORDS_TOOL_URI)
                response = await client.get(
                    f"{self.BASE_URL}{self.KEYWORDS_TOOL_URI}",
                    headers=headers,
                    params={"hintKeywords": ",".join(batch), "showDetail": "1"},
                )
                response.raise_for_status()
                data = response.json()
                for item in data.get("keywordList", []):
                    keyword = str(item.get("relKeyword") or "").strip()
                    if not keyword:
                        continue
                    metrics[keyword] = {
                        "monthly_pc_searches": self._to_int(item.get("monthlyPcQcCnt")),
                        "monthly_mobile_searches": self._to_int(item.get("monthlyMobileQcCnt")),
                        "monthly_pc_clicks": self._to_float(item.get("monthlyAvePcClkCnt")),
                        "monthly_mobile_clicks": self._to_float(item.get("monthlyAveMobileClkCnt")),
                        "monthly_pc_ctr": self._to_float(item.get("monthlyAvePcCtr")),
                        "monthly_mobile_ctr": self._to_float(item.get("monthlyAveMobileCtr")),
                        "competition_index": self._to_float(item.get("compIdx")),
                        "competition_level": self._to_competition_level(item.get("compIdx")),
                        "pl_avg_depth": self._to_float(item.get("plAvgDepth")),
                    }
        return metrics

    def _build_headers(self, *, method: str, uri: str) -> Dict[str, str]:
        timestamp = str(round(time.time() * 1000))
        signature = self._generate_signature(
            timestamp=timestamp,
            method=method,
            uri=uri,
            secret_key=self.settings.naver_ad_secret_key or "",
        )
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": str(self.settings.naver_ad_api_key),
            "X-Customer": str(self.settings.naver_ad_customer_id),
            "X-Signature": signature,
        }

    @staticmethod
    def _generate_signature(
        *,
        timestamp: str,
        method: str,
        uri: str,
        secret_key: str,
    ) -> str:
        message = f"{timestamp}.{method}.{uri}"
        digest = hmac.new(
            secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _chunk(items: List[str], size: int) -> List[List[str]]:
        return [items[index : index + size] for index in range(0, len(items), size)]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value in (None, "", "< 10"):
            return 0 if value == "< 10" else None
        try:
            return int(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, "", "< 0.1"):
            return 0.0 if value == "< 0.1" else None
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_competition_level(cls, value: Any) -> str | None:
        score = cls._to_float(value)
        if score is None:
            return None
        if score >= 1:
            return "높음"
        if score >= 0.34:
            return "중간"
        return "낮음"
