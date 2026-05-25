from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import get_settings

_LOCAL_CRAWLER_ROOT = Path(__file__).resolve().parents[2] / "local-crawler"


def _ensure_local_crawler_path() -> None:
    root = str(_LOCAL_CRAWLER_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


@dataclass
class China1688UrlResponse:
    status: str
    search_url: str = ""
    image_id: str = ""
    error: str = ""
    fetch_source: str = ""
    browser_country: str = ""


class China1688UrlService:
    _session: Optional[object] = None
    _session_ws: str = ""
    _lock = asyncio.Lock()
    _request_count = 0

    @classmethod
    def _resolve_ws_endpoint(cls) -> Tuple[str, str]:
        settings = get_settings()
        country = (settings.china_1688_browser_country or "KR").strip().upper()
        kr_ws = (settings.brightdata_browser_ws or "").strip()
        cn_ws = (settings.brightdata_browser_ws_1688 or "").strip()

        if country == "CN":
            ws = cn_ws or kr_ws
            label = "CN" if cn_ws else ("KR" if kr_ws else country)
        else:
            ws = kr_ws or cn_ws
            label = "KR" if kr_ws else ("CN" if cn_ws else country)

        return ws, label

    @classmethod
    def is_configured(cls) -> bool:
        ws, _ = cls._resolve_ws_endpoint()
        return bool(ws)

    @classmethod
    async def shutdown(cls) -> None:
        async with cls._lock:
            session = cls._session
            cls._session = None
            cls._session_ws = ""
            cls._request_count = 0
        if session is not None:
            await session.close()

    @classmethod
    async def _get_session(cls):
        _ensure_local_crawler_path()
        from services.alibaba_1688 import Warm1688UrlSession

        settings = get_settings()
        ws, country = cls._resolve_ws_endpoint()
        if not ws:
            raise RuntimeError(
                "Bright Data browser WS is not configured "
                "(set BRIGHTDATA_BROWSER_WS for KR or BRIGHTDATA_BROWSER_WS_1688 for CN)"
            )

        async with cls._lock:
            if cls._session is None or cls._session_ws != ws:
                if cls._session is not None:
                    await cls._session.close()
                    cls._session = None
                    cls._request_count = 0
                session = Warm1688UrlSession(
                    ws_endpoint=ws,
                    navigation_timeout_ms=int(settings.china_1688_navigation_timeout_ms or 120_000),
                )
                await session.open()
                cls._session = session
                cls._session_ws = ws
            return cls._session, country

    @classmethod
    async def generate_url(cls, image_url: str) -> China1688UrlResponse:
        image_url = str(image_url or "").strip()
        if not image_url:
            return China1688UrlResponse(status="NO_IMAGE", error="empty image_url")

        if not cls.is_configured():
            return China1688UrlResponse(
                status="NO_MATCH",
                error="Bright Data browser WS is not configured",
            )

        try:
            session, country = await cls._get_session()
            cls._request_count += 1
            result = await session.generate_url(
                image_url,
                reuse_home=True,
                use_cache=True,
                fast=True,
            )
        except Exception as exc:
            async with cls._lock:
                if cls._session is not None:
                    try:
                        await cls._session.close()
                    except Exception:
                        pass
                    cls._session = None
                    cls._session_ws = ""
            return China1688UrlResponse(
                status="NO_MATCH",
                error=f"{type(exc).__name__}: {exc}",
            )

        fetch_source = str(result.fetch_source or "")
        if country and fetch_source:
            fetch_source = f"{fetch_source}_{country.lower()}"

        return China1688UrlResponse(
            status=str(result.status or "NO_MATCH"),
            search_url=str(result.search_url or ""),
            image_id=str(result.image_id or ""),
            error=str(result.error or ""),
            fetch_source=fetch_source,
            browser_country=country,
        )
