from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, Dict, List

import httpx


class NaverSearchTrendService:
    SEARCH_TREND_URL = "https://openapi.naver.com/v1/datalab/search"
    RETRY_DELAYS = (2.0, 4.0, 8.0, 15.0)
    BATCH_DELAY_SECONDS = 1.5
    BATCH_SIZE = 3

    def __init__(self, settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.naver_client_id and self.settings.naver_client_secret)

    async def fetch_monthly_trends(self, keywords: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not self.is_configured or not keywords:
            return {}

        unique_keywords: List[str] = []
        seen = set()
        for keyword in keywords:
            value = str(keyword or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            unique_keywords.append(value)

        if not unique_keywords:
            return {}

        headers = {
            "X-Naver-Client-Id": str(self.settings.naver_client_id),
            "X-Naver-Client-Secret": str(self.settings.naver_client_secret),
            "Content-Type": "application/json",
        }

        end_date = date.today().replace(day=1)
        start_year = end_date.year - 1 if end_date.month < 12 else end_date.year
        start_month = end_date.month + 1 if end_date.month < 12 else 1
        start_date = date(start_year, start_month, 1)

        trends: Dict[str, List[Dict[str, Any]]] = {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            for batch in self._chunk(unique_keywords, self.BATCH_SIZE):
                payload = {
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "timeUnit": "month",
                    "keywordGroups": [
                        {"groupName": keyword, "keywords": [keyword]}
                        for keyword in batch
                    ],
                }
                response = await self._post_with_retry(
                    client=client,
                    headers=headers,
                    payload=payload,
                )
                data = response.json()
                for result in data.get("results", []):
                    keyword = str(result.get("title") or "").strip()
                    if keyword:
                        trends[keyword] = result.get("data") or []
                await asyncio.sleep(self.BATCH_DELAY_SECONDS)

        return trends

    async def _post_with_retry(
        self,
        *,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt, delay in enumerate(self.RETRY_DELAYS, start=1):
            response = await client.post(
                self.SEARCH_TREND_URL,
                headers=headers,
                json=payload,
            )
            last_response = response
            if response.status_code != 429:
                response.raise_for_status()
                return response
            if attempt < len(self.RETRY_DELAYS):
                await asyncio.sleep(self._resolve_retry_delay(response=response, fallback=delay))

        if last_response is not None:
            last_response.raise_for_status()
        raise RuntimeError("검색 트렌드 API 응답을 받지 못했습니다.")

    @staticmethod
    def _resolve_retry_delay(*, response: httpx.Response, fallback: float) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), fallback)
            except ValueError:
                return fallback
        return fallback

    @staticmethod
    def _chunk(items: List[str], size: int) -> List[List[str]]:
        return [items[index : index + size] for index in range(0, len(items), size)]
