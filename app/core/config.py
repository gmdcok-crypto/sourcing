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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
