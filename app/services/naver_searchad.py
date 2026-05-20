from __future__ import annotations

import base64
import hashlib
import hmac
import time
import asyncio
import re
import unicodedata
from typing import Any, Dict, List

import httpx


class NaverSearchAdService:
    BASE_URL = "https://api.searchad.naver.com"
    KEYWORDS_TOOL_URI = "/keywordstool"
    RETRY_DELAYS = (0.8, 1.6, 3.2)
    BATCH_DELAY_SECONDS = 0.35
    WHITESPACE_RE = re.compile(r"\s+")

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
        sanitized_keywords: List[str] = []
        sanitized_to_originals: Dict[str, List[str]] = {}
        seen = set()
        for keyword in keywords:
            original = str(keyword or "").strip()
            sanitized = self._sanitize_keyword(original)
            if not sanitized or sanitized in seen:
                continue
            seen.add(sanitized)
            sanitized_keywords.append(sanitized)
            sanitized_to_originals[sanitized] = [original]

        async with httpx.AsyncClient(timeout=20.0) as client:
            for batch in self._chunk(sanitized_keywords, 5):
                batch_metrics = await self._fetch_batch_metrics(
                    client=client,
                    batch=batch,
                )
                for sanitized_keyword, item_metrics in batch_metrics.items():
                    original_keywords = sanitized_to_originals.get(sanitized_keyword) or [sanitized_keyword]
                    for original_keyword in original_keywords:
                        metrics[original_keyword] = item_metrics
                await asyncio.sleep(self.BATCH_DELAY_SECONDS)
        return metrics

    async def _fetch_batch_metrics(
        self,
        *,
        client: httpx.AsyncClient,
        batch: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        if not batch:
            return {}

        headers = self._build_headers(method="GET", uri=self.KEYWORDS_TOOL_URI)
        params = {"hintKeywords": ",".join(batch), "showDetail": "1"}

        try:
            response = await self._get_with_retry(
                client=client,
                headers=headers,
                params=params,
            )
            return self._parse_metrics_response(response)
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 400 or len(batch) == 1:
                if len(batch) == 1 and error.response.status_code == 400:
                    return {}
                raise

        recovered_metrics: Dict[str, Dict[str, Any]] = {}
        for keyword in batch:
            headers = self._build_headers(method="GET", uri=self.KEYWORDS_TOOL_URI)
            params = {"hintKeywords": keyword, "showDetail": "1"}
            try:
                response = await self._get_with_retry(
                    client=client,
                    headers=headers,
                    params=params,
                )
                recovered_metrics.update(self._parse_metrics_response(response))
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 400:
                    raise
            await asyncio.sleep(0.1)
        return recovered_metrics

    async def _get_with_retry(
        self,
        *,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        params: Dict[str, str],
    ) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt, delay in enumerate(self.RETRY_DELAYS, start=1):
            response = await client.get(
                f"{self.BASE_URL}{self.KEYWORDS_TOOL_URI}",
                headers=headers,
                params=params,
            )
            last_response = response
            if response.status_code != 429:
                response.raise_for_status()
                return response
            if attempt < len(self.RETRY_DELAYS):
                await asyncio.sleep(delay)

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("SearchAd API 응답을 받지 못했습니다.")

    def _parse_metrics_response(self, response: httpx.Response) -> Dict[str, Dict[str, Any]]:
        data = response.json()
        metrics: Dict[str, Dict[str, Any]] = {}
        for item in data.get("keywordList", []):
            keyword = self._sanitize_keyword(str(item.get("relKeyword") or "").strip())
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
                "monthly_exposure_ads": self._to_int(item.get("monthlyAveDepth")),
            }
        return metrics

    @classmethod
    def _sanitize_keyword(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", str(value or ""))
        cleaned_chars = []
        for char in normalized:
            category = unicodedata.category(char)
            if category in {"Cc", "Cf", "Cs", "Co", "Cn"}:
                continue
            if char == ",":
                cleaned_chars.append(" ")
                continue
            cleaned_chars.append(char)
        cleaned = "".join(cleaned_chars).strip()
        return cls.WHITESPACE_RE.sub(" ", cleaned)

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
            text = str(value).replace(",", "").replace("%", "").strip()
            if not text:
                return None
            return float(text)
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
