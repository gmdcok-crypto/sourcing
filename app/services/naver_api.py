from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings

NAVER_SHOPPING_URL = "https://openapi.naver.com/v1/search/shop.json"
HTML_TAG_RE = re.compile(r"<[^>]+>")


class NaverShoppingService:
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
