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
    _session_country: str = ""
    _lock = asyncio.Lock()
    _request_count = 0

    @classmethod
    def _browser_country(cls) -> str:
        settings = get_settings()
        return (settings.china_1688_browser_country or "KR").strip().upper()

    @classmethod
    def _ws_candidates(cls) -> list[Tuple[str, str]]:
        settings = get_settings()
        kr_ws = (settings.brightdata_browser_ws or "").strip()
        cn_ws = (settings.brightdata_browser_ws_1688 or "").strip()
        country = cls._browser_country()

        if country == "CN":
            ordered = [("CN", cn_ws), ("KR", kr_ws)]
        else:
            ordered = [("KR", kr_ws), ("CN", cn_ws)]

        seen: set[str] = set()
        candidates: list[Tuple[str, str]] = []
        for label, ws in ordered:
            if not ws or ws in seen:
                continue
            seen.add(ws)
            candidates.append((label, ws))
        return candidates

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls._ws_candidates())

    @classmethod
    async def shutdown(cls) -> None:
        async with cls._lock:
            session = cls._session
            cls._session = None
            cls._session_ws = ""
            cls._session_country = ""
            cls._request_count = 0
        if session is not None:
            await session.close()

    @classmethod
    async def _open_session(cls, ws: str, country: str):
        _ensure_local_crawler_path()
        from services.alibaba_1688 import Warm1688UrlSession

        settings = get_settings()
        session = Warm1688UrlSession(
            ws_endpoint=ws,
            navigation_timeout_ms=int(settings.china_1688_navigation_timeout_ms or 120_000),
        )
        await session.open()
        return session

    @classmethod
    async def _get_session(cls):
        async with cls._lock:
            if cls._session is not None:
                return cls._session, cls._session_country

        last_error: Optional[Exception] = None
        for country, ws in cls._ws_candidates():
            try:
                session = await cls._open_session(ws, country)
            except Exception as exc:
                last_error = exc
                continue

            async with cls._lock:
                cls._session = session
                cls._session_ws = ws
                cls._session_country = country
                cls._request_count = 0
            return session, country

        if last_error is not None:
            raise last_error
        raise RuntimeError(
            "Bright Data browser WS is not configured "
            "(set BRIGHTDATA_BROWSER_WS for KR or BRIGHTDATA_BROWSER_WS_1688 for CN)"
        )

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
                use_cache=False,
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
                    cls._session_country = ""
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
