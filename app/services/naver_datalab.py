from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

import httpx


@dataclass
class CategoryKeywordFetchResult:
    keywords: List[Dict[str, Any]]
    source: str


class NaverShoppingInsightService:
    BASE_URL = "https://datalab.naver.com"
    OPENAPI_BASE_URL = "https://openapi.naver.com/v1/datalab/shopping"
    CATEGORY_PAGE_URL = f"{BASE_URL}/shoppingInsight/sCategory.naver"
    OPENAPI_CATEGORY_KEYWORDS_URL = f"{OPENAPI_BASE_URL}/category/keywords"
    RANK_ENDPOINT_CANDIDATES = (
        f"{BASE_URL}/shoppingInsight/getCategoryKeywordRank.naver",
        f"{BASE_URL}/shoppingInsight/getCategoryKeywordRankAjax.naver",
        f"{BASE_URL}/shoppingInsight/getKeywordRank.naver",
    )

    def __init__(self, settings) -> None:
        self.settings = settings

    async def fetch_category_top_keywords(
        self,
        *,
        cid: str,
        seed_keywords: List[str] | None = None,
        limit: int = 150,
    ) -> CategoryKeywordFetchResult:
        try:
            keywords = await self._fetch_category_top_keywords_from_web(cid=cid, limit=limit)
            return CategoryKeywordFetchResult(keywords=keywords, source="shopping_insight_web")
        except Exception:
            if not seed_keywords:
                raise
            keywords = await self._fetch_category_top_keywords_from_openapi(
                cid=cid,
                seed_keywords=seed_keywords,
                limit=limit,
            )
            return CategoryKeywordFetchResult(keywords=keywords, source="shopping_insight_openapi")

    async def _fetch_category_top_keywords_from_web(
        self,
        *,
        cid: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        page_size = 20
        page = 1
        collected: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": f"{self.CATEGORY_PAGE_URL}?cid={cid}",
                "Origin": self.BASE_URL,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/136.0.0.0 Safari/537.36"
                ),
            },
        ) as client:
            await client.get(self.CATEGORY_PAGE_URL, params={"cid": cid})
            client.cookies.set("_datalab_cid", cid, domain="datalab.naver.com", path="/")

            while len(collected) < limit:
                payload = self._build_request_payload(cid=cid, page=page, count=page_size)
                response_data = await self._request_rank_page(client=client, payload=payload)
                ranks = response_data.get("ranks") or response_data.get("result") or []
                if not isinstance(ranks, list) or not ranks:
                    break

                for row in ranks:
                    keyword = str(row.get("keyword") or "").strip()
                    if not keyword:
                        continue
                    collected.append(
                        {
                            "rank": self._to_int(row.get("rank")) or len(collected) + 1,
                            "keyword": keyword,
                            "ratio": self._to_float(row.get("ratio")),
                        }
                    )
                    if len(collected) >= limit:
                        break

                if len(ranks) < page_size:
                    break

                page += 1

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for row in collected:
            keyword = row["keyword"]
            if keyword in seen:
                continue
            seen.add(keyword)
            deduped.append(row)
            if len(deduped) >= limit:
                break
        return deduped

    async def _fetch_category_top_keywords_from_openapi(
        self,
        *,
        cid: str,
        seed_keywords: List[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not self.settings.naver_client_id or not self.settings.naver_client_secret:
            raise RuntimeError("Naver DataLab open API credentials are not configured.")

        candidates = []
        seen = set()
        for keyword in seed_keywords:
            value = str(keyword or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            candidates.append(value)
            if len(candidates) >= max(limit, 30):
                break

        if not candidates:
            return []

        headers = {
            "X-Naver-Client-Id": self.settings.naver_client_id,
            "X-Naver-Client-Secret": self.settings.naver_client_secret,
            "Content-Type": "application/json",
        }
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=30)
        scored_rows: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            for batch in self._chunk(candidates, 5):
                payload = {
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                    "timeUnit": "date",
                    "category": cid,
                    "keyword": [
                        {"name": keyword, "param": [keyword]}
                        for keyword in batch
                    ],
                    "device": "",
                    "gender": "",
                    "ages": [],
                }
                response = await client.post(
                    self.OPENAPI_CATEGORY_KEYWORDS_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                for result in data.get("results", []):
                    keyword_name = str(result.get("title") or "").strip()
                    points = result.get("data") or []
                    ratios = [
                        self._to_float(point.get("ratio"))
                        for point in points
                        if self._to_float(point.get("ratio")) is not None
                    ]
                    if not keyword_name or not ratios:
                        continue
                    latest_ratio = ratios[-1]
                    peak_ratio = max(ratios)
                    avg_ratio = sum(ratios) / len(ratios)
                    score = (latest_ratio * 0.6) + (peak_ratio * 0.3) + (avg_ratio * 0.1)
                    scored_rows.append(
                        {
                            "keyword": keyword_name,
                            "ratio": round(score, 5),
                            "latest_ratio": latest_ratio,
                            "peak_ratio": peak_ratio,
                            "avg_ratio": round(avg_ratio, 5),
                            "source": "shopping_insight_openapi",
                        }
                    )

        scored_rows.sort(
            key=lambda item: (
                -(item.get("ratio") or 0.0),
                -(item.get("peak_ratio") or 0.0),
                item.get("keyword") or "",
            )
        )
        for index, row in enumerate(scored_rows, start=1):
            row["rank"] = index
        return scored_rows[:limit]

    async def _request_rank_page(
        self,
        *,
        client: httpx.AsyncClient,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        last_error: str | None = None
        for url in self.RANK_ENDPOINT_CANDIDATES:
            response = await client.post(url, data=payload)
            if response.status_code == 404:
                last_error = f"{url} returned 404"
                continue
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower():
                body_preview = response.text[:120].strip()
                last_error = f"{url} returned non-json response: {body_preview}"
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(last_error or "쇼핑 인사이트 랭킹 엔드포인트를 찾지 못했습니다.")

    @staticmethod
    def _build_request_payload(*, cid: str, page: int, count: int) -> Dict[str, Any]:
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=30)
        return {
            "cid": cid,
            "timeUnit": "date",
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "device": "",
            "gender": "",
            "age": "",
            "page": str(page),
            "count": str(count),
        }

    @staticmethod
    def _chunk(items: List[str], size: int) -> List[List[str]]:
        return [items[index : index + size] for index in range(0, len(items), size)]

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value in (None, ""):
                return None
            return int(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            return float(str(value))
        except (TypeError, ValueError):
            return None
