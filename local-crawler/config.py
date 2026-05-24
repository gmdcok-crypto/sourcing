from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalCrawlerSettings(BaseSettings):
    manual_keyword: Optional[str] = Field(default=None, alias="MANUAL_KEYWORD")

    railway_api_base_url: str = Field(..., alias="RAILWAY_API_BASE_URL")
    crawler_keywords_endpoint: str = Field(
        default="/api/admin/keyword-sourcing/crawler-keywords",
        alias="CRAWLER_KEYWORDS_ENDPOINT",
    )
    crawler_keywords_limit: int = Field(default=10, alias="CRAWLER_KEYWORDS_LIMIT")
    crawler_run_id: Optional[str] = Field(default=None, alias="CRAWLER_RUN_ID")
    crawler_date_value: Optional[str] = Field(default=None, alias="CRAWLER_DATE_VALUE")
    mysql_url: Optional[str] = Field(default=None, alias="MYSQL_URL")
    mysql_public_url: Optional[str] = Field(default=None, alias="MYSQL_PUBLIC_URL")
    mariadb_public_url: Optional[str] = Field(default=None, alias="MARIADB_PUBLIC_URL")
    r2_account_id: Optional[str] = Field(default=None, alias="R2_ACCOUNT_ID")
    r2_access_key_id: Optional[str] = Field(default=None, alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: Optional[str] = Field(default=None, alias="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: Optional[str] = Field(default=None, alias="R2_BUCKET_NAME")
    r2_public_base_url: Optional[str] = Field(default=None, alias="R2_PUBLIC_BASE_URL")

    brightdata_api_token: Optional[str] = Field(default=None, alias="BRIGHTDATA_API_TOKEN")
    brightdata_request_zone: Optional[str] = Field(default=None, alias="BRIGHTDATA_REQUEST_ZONE")
    brightdata_browser_ws_1688: Optional[str] = Field(
        default=None, alias="BRIGHTDATA_BROWSER_WS_1688"
    )
    china_search_top_n: int = Field(default=8, alias="CHINA_SEARCH_TOP_N")
    china_fx_cny_to_krw: float = Field(default=185.0, alias="CHINA_FX_CNY_TO_KRW")
    china_search_sleep_sec: float = Field(default=3.0, alias="CHINA_SEARCH_SLEEP_SEC")
    coupang_bright_request: str = Field(default="off", alias="COUPANG_BRIGHT_REQUEST")

    crawler_headless: bool = Field(default=True, alias="CRAWLER_HEADLESS")
    crawler_navigation_timeout_ms: int = Field(default=90000, alias="CRAWLER_NAVIGATION_TIMEOUT_MS")
    crawler_action_timeout_ms: int = Field(default=30000, alias="CRAWLER_ACTION_TIMEOUT_MS")
    crawler_result_limit: int = Field(default=10, alias="CRAWLER_RESULT_LIMIT")
    crawler_detail_limit: int = Field(default=3, alias="CRAWLER_DETAIL_LIMIT")
    crawler_scroll_steps_min: int = Field(default=3, alias="CRAWLER_SCROLL_STEPS_MIN")
    crawler_scroll_steps_max: int = Field(default=6, alias="CRAWLER_SCROLL_STEPS_MAX")
    crawler_sleep_min_seconds: int = Field(default=3, alias="CRAWLER_SLEEP_MIN_SECONDS")
    crawler_sleep_max_seconds: int = Field(default=5, alias="CRAWLER_SLEEP_MAX_SECONDS")
    ui_refresh_seconds: int = Field(default=5, alias="UI_REFRESH_SECONDS")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> LocalCrawlerSettings:
    return LocalCrawlerSettings()
