from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings


class R2StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return all(
            [
                self.settings.r2_account_id,
                self.settings.r2_access_key_id,
                self.settings.r2_secret_access_key,
                self.settings.r2_bucket_name,
            ]
        )

    def save_search_result(self, *, query: str, payload: Dict[str, Any]) -> Optional[str]:
        if not self.is_configured():
            return None

        key = self._build_key(query=query)
        endpoint_url = (
            f"https://{self.settings.r2_account_id}.r2.cloudflarestorage.com"
        )
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name="auto",
        )

        try:
            client.put_object(
                Bucket=self.settings.r2_bucket_name,
                Key=key,
                Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except (BotoCoreError, ClientError):
            return None

        return key

    def _build_key(self, *, query: str) -> str:
        safe_query = "-".join(query.strip().lower().split()) or "empty-query"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"search-results/{safe_query}/{timestamp}.json"
