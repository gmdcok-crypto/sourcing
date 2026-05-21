from functools import lru_cache
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

    brightdata_proxy_host: str = Field(default="brd.superproxy.io", alias="BRIGHTDATA_PROXY_HOST")
    brightdata_proxy_port: int = Field(default=33335, alias="BRIGHTDATA_PROXY_PORT")
    brightdata_proxy_username: str = Field(..., alias="BRIGHTDATA_PROXY_USERNAME")
    brightdata_proxy_password: str = Field(..., alias="BRIGHTDATA_PROXY_PASSWORD")
    brightdata_proxy_country: str = Field(default="kr", alias="BRIGHTDATA_PROXY_COUNTRY")
    brightdata_proxy_session_prefix: str = Field(default="local-crawler", alias="BRIGHTDATA_PROXY_SESSION_PREFIX")

    crawler_headless: bool = Field(default=True, alias="CRAWLER_HEADLESS")
    crawler_navigation_timeout_ms: int = Field(default=90000, alias="CRAWLER_NAVIGATION_TIMEOUT_MS")
    crawler_action_timeout_ms: int = Field(default=30000, alias="CRAWLER_ACTION_TIMEOUT_MS")
    crawler_result_limit: int = Field(default=10, alias="CRAWLER_RESULT_LIMIT")
    crawler_detail_limit: int = Field(default=3, alias="CRAWLER_DETAIL_LIMIT")
    crawler_scroll_steps_min: int = Field(default=3, alias="CRAWLER_SCROLL_STEPS_MIN")
    crawler_scroll_steps_max: int = Field(default=6, alias="CRAWLER_SCROLL_STEPS_MAX")
    crawler_sleep_min_seconds: int = Field(default=3, alias="CRAWLER_SLEEP_MIN_SECONDS")
    crawler_sleep_max_seconds: int = Field(default=5, alias="CRAWLER_SLEEP_MAX_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> LocalCrawlerSettings:
    return LocalCrawlerSettings()
