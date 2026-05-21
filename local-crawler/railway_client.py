from typing import Any, Dict, List, Optional

import httpx

from config import LocalCrawlerSettings


class RailwayKeywordClient:
    def __init__(self, settings: LocalCrawlerSettings) -> None:
        self.settings = settings

    def fetch_keywords(self, *, limit: Optional[int] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "limit": int(limit or self.settings.crawler_keywords_limit),
        }
        if self.settings.crawler_run_id:
            params["run_id"] = self.settings.crawler_run_id
        if self.settings.crawler_date_value:
            params["date_value"] = self.settings.crawler_date_value

        url = f"{self.settings.railway_api_base_url.rstrip('/')}{self.settings.crawler_keywords_endpoint}"
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def fetch_keyword_list(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        payload = self.fetch_keywords(limit=limit)
        keywords = payload.get("keywords")
        if isinstance(keywords, list):
            return keywords
        return []
