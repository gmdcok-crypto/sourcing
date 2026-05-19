from __future__ import annotations

import io
import json
from datetime import date, datetime, timezone
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
        client = self._build_client()

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

    def save_json_bytes(
        self,
        *,
        key: str,
        payload: Dict[str, Any],
    ) -> Optional[str]:
        if not self.is_configured():
            return None

        client = self._build_client()

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

    def save_binary(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
    ) -> Optional[str]:
        if not self.is_configured():
            return None

        client = self._build_client()

        try:
            client.put_object(
                Bucket=self.settings.r2_bucket_name,
                Key=key,
                Body=body,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError):
            return None

        return key

    def save_dataframe_parquet(self, *, key: str, dataframe) -> Optional[str]:
        buffer = io.BytesIO()
        try:
            dataframe.to_parquet(buffer, index=False)
        except Exception:
            return None

        return self.save_binary(
            key=key,
            body=buffer.getvalue(),
            content_type="application/octet-stream",
        )

    def read_json(self, *, key: str) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None

        client = self._build_client()
        try:
            response = client.get_object(Bucket=self.settings.r2_bucket_name, Key=key)
            body = response["Body"].read().decode("utf-8")
        except (BotoCoreError, ClientError, KeyError, UnicodeDecodeError):
            return None

        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    def find_latest_json_key_for_date(self, *, target_date: date) -> Optional[str]:
        if not self.is_configured():
            return None

        client = self._build_client()
        prefix = "search-results/raw/"
        continuation_token = None
        matching_keys = []
        date_token = target_date.strftime("%Y%m%d")

        try:
            while True:
                kwargs = {
                    "Bucket": self.settings.r2_bucket_name,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token
                response = client.list_objects_v2(**kwargs)

                for item in response.get("Contents", []):
                    key = item.get("Key") or ""
                    name = key.rsplit("/", 1)[-1]
                    if name.startswith(date_token) and name.endswith(".json"):
                        matching_keys.append(key)

                if not response.get("IsTruncated"):
                    break
                continuation_token = response.get("NextContinuationToken")
        except (BotoCoreError, ClientError):
            return None

        if not matching_keys:
            return None
        matching_keys.sort(reverse=True)
        return matching_keys[0]

    def _build_key(self, *, query: str) -> str:
        safe_query = "-".join(query.strip().lower().split()) or "empty-query"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"search-results/{safe_query}/{timestamp}.json"

    def _build_client(self):
        endpoint_url = f"https://{self.settings.r2_account_id}.r2.cloudflarestorage.com"
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=self.settings.r2_access_key_id,
            aws_secret_access_key=self.settings.r2_secret_access_key,
            region_name="auto",
        )
