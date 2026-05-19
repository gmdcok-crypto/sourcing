from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import httpx


class NaverSearchTrendService:
    SEARCH_TREND_URL = "https://openapi.naver.com/v1/datalab/search"

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
            for batch in self._chunk(unique_keywords, 5):
                payload = {
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "timeUnit": "month",
                    "keywordGroups": [
                        {"groupName": keyword, "keywords": [keyword]}
                        for keyword in batch
                    ],
                }
                response = await client.post(
                    self.SEARCH_TREND_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                for result in data.get("results", []):
                    keyword = str(result.get("title") or "").strip()
                    if keyword:
                        trends[keyword] = result.get("data") or []

        return trends

    @staticmethod
    def _chunk(items: List[str], size: int) -> List[List[str]]:
        return [items[index : index + size] for index in range(0, len(items), size)]
