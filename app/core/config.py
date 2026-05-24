from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sourcing API"
    app_env: str = "development"
    app_debug: bool = False
    api_prefix: str = "/api"
    mysql_url: Optional[str] = Field(default=None, alias="MYSQL_URL")

    naver_client_id: Optional[str] = Field(default=None, alias="NAVER_CLIENT_ID")
    naver_client_secret: Optional[str] = Field(
        default=None,
        alias="NAVER_CLIENT_SECRET",
    )
    naver_ad_api_key: Optional[str] = Field(default=None, alias="NAVER_AD_API_KEY")
    naver_ad_secret_key: Optional[str] = Field(
        default=None,
        alias="NAVER_AD_SECRET_KEY",
    )
    naver_ad_customer_id: Optional[str] = Field(
        default=None,
        alias="NAVER_AD_CUSTOMER_ID",
    )

    r2_account_id: Optional[str] = Field(default=None, alias="R2_ACCOUNT_ID")
    r2_access_key_id: Optional[str] = Field(default=None, alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: Optional[str] = Field(
        default=None,
        alias="R2_SECRET_ACCESS_KEY",
    )
    r2_bucket_name: Optional[str] = Field(default=None, alias="R2_BUCKET_NAME")
    r2_public_base_url: Optional[str] = Field(default=None, alias="R2_PUBLIC_BASE_URL")

    bright_data_api_key: Optional[str] = Field(
        default=None,
        alias="BRIGHT_DATA_API_KEY",
    )
    bright_data_zone: Optional[str] = Field(default=None, alias="BRIGHT_DATA_ZONE")
    brightdata_browser_ws: Optional[str] = Field(default=None, alias="BRIGHTDATA_BROWSER_WS")
    brightdata_browser_ws_1688: Optional[str] = Field(
        default=None, alias="BRIGHTDATA_BROWSER_WS_1688"
    )
    china_1688_navigation_timeout_ms: int = Field(
        default=120_000, alias="CHINA_1688_NAVIGATION_TIMEOUT_MS"
    )
    brightdata_country: str = Field(default="KR", alias="BRIGHTDATA_COUNTRY")
    brightdata_session_prefix: str = Field(default="coupang", alias="BRIGHTDATA_SESSION_PREFIX")
    brightdata_timeout: int = Field(default=60, alias="BRIGHTDATA_TIMEOUT")
    brightdata_max_retries: int = Field(default=2, alias="BRIGHTDATA_MAX_RETRIES")
    brightdata_headless: bool = Field(default=True, alias="BRIGHTDATA_HEADLESS")
    brightdata_slow_mo_ms: int = Field(default=250, alias="BRIGHTDATA_SLOW_MO_MS")
    brightdata_navigation_timeout: int = Field(default=90000, alias="BRIGHTDATA_NAVIGATION_TIMEOUT")
    brightdata_action_timeout: int = Field(default=30000, alias="BRIGHTDATA_ACTION_TIMEOUT")
    coupang_result_limit: int = Field(default=10, alias="COUPANG_RESULT_LIMIT")
    coupang_detail_limit: int = Field(default=10, alias="COUPANG_DETAIL_LIMIT")
    coupang_sleep_min_seconds: int = Field(default=3, alias="COUPANG_SLEEP_MIN_SECONDS")
    coupang_sleep_max_seconds: int = Field(default=5, alias="COUPANG_SLEEP_MAX_SECONDS")
    coupang_scroll_steps_min: int = Field(default=3, alias="COUPANG_SCROLL_STEPS_MIN")
    coupang_scroll_steps_max: int = Field(default=6, alias="COUPANG_SCROLL_STEPS_MAX")

    model_config = SettingsConfigDict(
        env_file=(".env", "local-crawler/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
