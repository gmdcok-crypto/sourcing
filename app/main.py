from typing import Any, Dict

from fastapi import FastAPI

from app.api.routes_keywords import router as keyword_router
from app.core.config import get_settings
from app.services.brightdata import BrightDataService

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.1.0",
)

app.include_router(keyword_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> Dict[str, str]:
    return {
        "message": "Sourcing API is running.",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    bright_data_service = BrightDataService(settings)
    return {
        "status": "ok",
        "environment": settings.app_env,
        "bright_data": bright_data_service.get_status(),
        "r2_configured": bool(
            settings.r2_account_id
            and settings.r2_access_key_id
            and settings.r2_secret_access_key
            and settings.r2_bucket_name
        ),
        "naver_configured": bool(
            settings.naver_client_id and settings.naver_client_secret
        ),
    }
