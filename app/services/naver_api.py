from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings

NAVER_SHOPPING_URL = "https://openapi.naver.com/v1/search/shop.json"
HTML_TAG_RE = re.compile(r"<[^>]+>")


class NaverShoppingService:
    RETRY_DELAYS = (0.6, 1.2, 2.4)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search_products(
        self,
        *,
        query: str,
        display: int = 10,
        start: int = 1,
        sort: str = "sim",
    ) -> dict[str, Any]:
        if not self.settings.naver_client_id or not self.settings.naver_client_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Naver API credentials are not configured.",
            )

        headers = {
            "X-Naver-Client-Id": self.settings.naver_client_id,
            "X-Naver-Client-Secret": self.settings.naver_client_secret,
        }
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": sort,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(NAVER_SHOPPING_URL, headers=headers, params=params)

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail={
                    "message": "Failed to fetch Naver shopping results.",
                    "naver_response": response.text,
                },
            )

        data = response.json()
        data["items"] = [self._normalize_item(item) for item in data.get("items", [])]
        return data

    async def fetch_product_infos(self, keywords: List[str]) -> Dict[str, Dict[str, Any]]:
        if not self.settings.naver_client_id or not self.settings.naver_client_secret:
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

        headers = self._build_headers()
        semaphore = asyncio.Semaphore(5)
        infos: Dict[str, Dict[str, Any]] = {}

        async def fetch_info(client: httpx.AsyncClient, keyword: str) -> None:
            async with semaphore:
                total = 0
                category_path = ""
                for attempt, delay in enumerate(self.RETRY_DELAYS, start=1):
                    try:
                        response = await client.get(
                            NAVER_SHOPPING_URL,
                            headers=headers,
                            params={
                                "query": keyword,
                                "display": 1,
                                "start": 1,
                                "sort": "sim",
                            },
                        )
                        if response.status_code == 429 and attempt < len(self.RETRY_DELAYS):
                            await asyncio.sleep(delay)
                            continue
                        response.raise_for_status()
                        data = response.json()
                        total = int(data.get("total") or 0)
                        items = data.get("items") or []
                        if items:
                            item = items[0] or {}
                            categories = [
                                item.get("category1"),
                                item.get("category2"),
                                item.get("category3"),
                                item.get("category4"),
                            ]
                            category_path = " > ".join(str(value).strip() for value in categories if value)
                        break
                    except Exception:
                        if attempt < len(self.RETRY_DELAYS):
                            await asyncio.sleep(delay)
                            continue
                        total = 0
                        category_path = ""
                infos[keyword] = {
                    "product_count": total,
                    "category_path": category_path,
                }

        async with httpx.AsyncClient(timeout=20.0) as client:
            await asyncio.gather(*(fetch_info(client, keyword) for keyword in unique_keywords))

        return infos

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        normalized["title"] = self._strip_html(item.get("title", ""))
        normalized["mall_name"] = item.get("mallName")
        normalized["product_id"] = item.get("productId")
        normalized["product_type"] = item.get("productType")
        return normalized

    @staticmethod
    def _strip_html(value: str) -> str:
        return HTML_TAG_RE.sub("", value)

    def _build_headers(self) -> Dict[str, str]:
        return {
            "X-Naver-Client-Id": str(self.settings.naver_client_id),
            "X-Naver-Client-Secret": str(self.settings.naver_client_secret),
        }
