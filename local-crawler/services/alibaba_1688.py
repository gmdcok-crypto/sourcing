from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import requests
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config import LocalCrawlerSettings, get_settings
from services.price_1688 import extract_prices_from_text_blob, parse_price_cny, summarize_prices

_ROBOTS_BLOCKED_MARKERS = ("robots.txt", "brob", "is restricted")
_IMAGE_SEARCH_URL_RE = re.compile(
    r"(youyuan/index\.htm|search\.1688\.com/youyuan).*imageId=\d+",
    re.IGNORECASE,
)
_EMPTY_RESULT_MARKERS = ("空空如也",)
_IMAGE_SEARCH_BODY_MARKERS = ("为您找到", "结果中搜索")


@dataclass
class ChinaSearchResult:
    status: str
    image_url: str
    match_count: int = 0
    avg_price_cny: Optional[float] = None
    avg_price_krw: Optional[float] = None
    prices_cny: List[float] = field(default_factory=list)
    sample_titles: List[str] = field(default_factory=list)
    error: str = ""
    search_url: str = ""
    fetch_source: str = ""
    image_id: str = ""


def build_image_search_urls(image_url: str) -> List[str]:
    encoded = quote(image_url, safe="")
    return [
        f"https://s.1688.com/youyuan/index.htm?imageAddress={encoded}",
    ]


async def _download_image_bytes(image_url: str, *, timeout: float = 30.0) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.coupang.com/",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(image_url, headers=headers)
        response.raise_for_status()
        return response.content


def _fetch_html_via_unlocker(
    url: str,
    *,
    settings: LocalCrawlerSettings,
) -> Optional[str]:
    token = (settings.brightdata_api_token or "").strip()
    zone = (settings.brightdata_request_zone or "").strip()
    if not token or not zone:
        return None
    payload = {
        "zone": zone,
        "url": url,
        "format": "raw",
        "country": "cn",
    }
    try:
        response = requests.post(
            "https://api.brightdata.com/request",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=60,
        )
    except Exception:
        return None
    if response.status_code != 200:
        return None
    text = (response.text or "").strip()
    return text if text and "<" in text else None


def _result_from_html(
    *,
    html: str,
    image_url: str,
    search_url: str,
    fetch_source: str,
    top_n: int,
) -> ChinaSearchResult:
    if "空空如也" in html or "empty" in html.lower() and "offer" not in html.lower():
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="empty_search_results",
            search_url=search_url,
            fetch_source=fetch_source,
        )

    prices = extract_prices_from_text_blob(html, limit=top_n * 4)
    if not prices:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="no_prices_in_html",
            search_url=search_url,
            fetch_source=fetch_source,
        )

    sample_titles = re.findall(r'"subject"\s*:\s*"([^"]{4,80})"', html)[:5]
    if not sample_titles:
        sample_titles = re.findall(r'offerTitle[^>]*>([^<]{4,80})<', html)[:5]

    avg_cny = summarize_prices(prices, top_n=top_n)
    return ChinaSearchResult(
        status="OK",
        image_url=image_url,
        match_count=len(prices[:top_n]),
        avg_price_cny=avg_cny,
        prices_cny=prices[:top_n],
        sample_titles=sample_titles,
        search_url=search_url,
        fetch_source=fetch_source,
    )


async def _extract_offer_cards(page: Page) -> Dict[str, Any]:
    return await page.evaluate(
        """
        () => {
          const selectors = [
            '.offer-card',
            '.sm-offer-item',
            '.offer-item',
            '.gallery-offer-card',
            '[data-offer-id]',
            '.space-offer-card-box',
            '.offer-card-container',
          ];
          const nodes = [];
          for (const sel of selectors) {
            document.querySelectorAll(sel).forEach((el) => nodes.push(el));
          }
          const unique = Array.from(new Set(nodes));
          const cards = [];
          for (const el of unique.slice(0, 30)) {
            const text = (el.innerText || '').trim();
            const link = el.querySelector('a[href*="offer"], a[href*="detail.1688"]');
            const titleNode = el.querySelector(
              '.title, .offer-title, [class*="title"], a'
            );
            cards.push({
              text,
              title: titleNode ? (titleNode.textContent || '').trim() : '',
              href: link ? link.href : '',
            });
          }
          return {
            cardCount: cards.length,
            cards,
            bodyPreview: (document.body && document.body.innerText || '').slice(0, 16000),
            pageUrl: location.href,
          };
        }
        """
    )


async def _scroll_results(page: Page, *, steps: int = 4) -> None:
    for _ in range(steps):
        await page.mouse.wheel(0, 1400)
        await asyncio.sleep(0.8)


def _collect_prices_from_cards(cards: List[Dict[str, Any]], *, top_n: int) -> List[float]:
    prices: List[float] = []
    for card in cards:
        price = parse_price_cny(str(card.get("text") or ""))
        if price is not None:
            prices.append(price)
        if len(prices) >= top_n:
            break
    return prices


def _is_image_search_url(url: str) -> bool:
    return bool(_IMAGE_SEARCH_URL_RE.search(str(url or "")))


def _build_image_search_url(image_id: str, *, source_image_url: str = "") -> str:
    image_id = str(image_id or "").strip()
    params = [
        "tab=imageSearch",
        f"imageId={image_id}",
        f"imageIdList={image_id}",
        "spm=a260k.home2025.imagesearch.upload",
    ]
    source_image_url = str(source_image_url or "").strip()
    if source_image_url:
        params.append(f"imageAddress={quote(source_image_url, safe='')}")
    return "https://s.1688.com/youyuan/index.htm?" + "&".join(params)


def _extract_image_id_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for pattern in (
        re.compile(r'"imageId"\s*:\s*"?(\d{10,})"?'),
        re.compile(r"imageId=(\d{10,})"),
        re.compile(r"imageIdList=(\d{10,})"),
    ):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


async def _find_image_search_page(
    page: Page,
    context: BrowserContext,
    *,
    timeout_ms: int,
) -> Optional[Page]:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        for candidate in context.pages:
            try:
                if _is_image_search_url(candidate.url):
                    return candidate
            except Exception:
                continue
        try:
            if _is_image_search_url(page.url):
                return page
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return None


async def _click_search_image_button(page: Page) -> bool:
    button = page.get_by_text("搜索图片", exact=False)
    if await button.count():
        await button.first.click()
        return True
    return bool(
        await page.evaluate(
            """
            () => {
              const nodes = Array.from(document.querySelectorAll('button,a,span,div'));
              const target = nodes.find((el) => (el.textContent || '').includes('搜索图片'));
              if (!target) return false;
              target.click();
              return true;
            }
            """
        )
    )


async def _wait_for_home_upload_ready(page: Page, *, timeout_ms: int, fast: bool = False) -> None:
    upload_marker = page.get_by_text(re.compile(r"已上传\s*\d+\s*张图片"))
    try:
        await upload_marker.first.wait_for(state="visible", timeout=timeout_ms)
        return
    except Exception:
        if not fast:
            await asyncio.sleep(2)


async def _open_image_search_results_page(
    page: Page,
    context: BrowserContext,
    *,
    navigation_timeout_ms: int,
    captured_image_ids: Optional[List[str]] = None,
) -> Page:
    existing = await _find_image_search_page(page, context, timeout_ms=500)
    if existing is not None:
        return existing

    popup_timeout_ms = min(8000, navigation_timeout_ms)
    clicked = False
    try:
        async with context.expect_page(timeout=popup_timeout_ms) as popup_info:
            if not await _click_search_image_button(page):
                raise RuntimeError("search_image_button_not_found")
            clicked = True
        popup_page = await popup_info.value
        found = await _find_image_search_page(popup_page, context, timeout_ms=navigation_timeout_ms)
        if found is not None:
            return found
    except Exception:
        if not clicked and not _is_image_search_url(page.url):
            if not await _click_search_image_button(page):
                raise RuntimeError("search_image_button_not_found")

    found = await _find_image_search_page(page, context, timeout_ms=navigation_timeout_ms)
    if found is not None:
        return found

    if captured_image_ids:
        target_url = _build_image_search_url(captured_image_ids[-1])
        await page.goto(target_url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
        if _is_image_search_url(page.url):
            return page

    raise TimeoutError("image_search_navigation_timeout")


def _result_from_image_search_page(
    *,
    payload: Dict[str, Any],
    image_url: str,
    page_url: str,
    body_preview: str,
    top_n: int,
    fetch_source: str,
) -> ChinaSearchResult:
    if not _is_image_search_url(page_url):
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="image_search_navigation_timeout",
            search_url=page_url,
            fetch_source=fetch_source,
        )

    if any(marker in body_preview for marker in _EMPTY_RESULT_MARKERS):
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="empty_search_results",
            search_url=page_url,
            fetch_source=fetch_source,
        )

    cards = list(payload.get("cards") or [])
    prices = _collect_prices_from_cards(cards, top_n=top_n)
    if len(prices) < 2:
        prices = extract_prices_from_text_blob(body_preview, limit=top_n * 4)[:top_n]

    if not prices:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="image_search_no_prices",
            search_url=page_url,
            fetch_source=fetch_source,
        )

    on_results_page = any(marker in body_preview for marker in _IMAGE_SEARCH_BODY_MARKERS)
    status = "OK" if on_results_page else "LOW_CONFIDENCE"
    error = "" if on_results_page else "image_search_low_confidence_body"

    return ChinaSearchResult(
        status=status,
        image_url=image_url,
        match_count=len(prices),
        avg_price_cny=summarize_prices(prices, top_n=top_n, min_price=1.0),
        prices_cny=prices[:top_n],
        sample_titles=[
            str(card.get("title") or "").strip()
            for card in cards
            if str(card.get("title") or "").strip()
        ][:5],
        search_url=page_url,
        fetch_source=fetch_source,
        error=error,
    )


async def _parse_image_search_page(
    page: Page,
    image_url: str,
    *,
    top_n: int,
    fetch_source: str,
) -> ChinaSearchResult:
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    await _scroll_results(page)
    payload = await _extract_offer_cards(page)
    page_url = str(payload.get("pageUrl") or page.url)
    body_preview = str(payload.get("bodyPreview") or "")
    return _result_from_image_search_page(
        payload=payload,
        image_url=image_url,
        page_url=page_url,
        body_preview=body_preview,
        top_n=top_n,
        fetch_source=fetch_source,
    )


async def _extract_image_id_from_page(page: Page) -> Optional[str]:
    try:
        image_id = _extract_image_id_from_text(page.url)
        if image_id:
            return image_id
        html = await page.content()
        return _extract_image_id_from_text(html[:80000])
    except Exception:
        return None


async def _capture_image_id_from_response(response: Any, *, upload_started: bool) -> Optional[str]:
    if not upload_started:
        return None
    url = str(response.url or "")
    if not any(
        token in url
        for token in (
            "getSearchImageUpload",
            "imageSearchOfferResultViewService",
            "wirelessrecommend.recommend",
            "mtop.relationrecommend",
            "mtop.alibaba",
            "imageSearch",
            "ImageUpload",
            "searchImage",
        )
    ):
        return None
    try:
        body_text = f"{url}\n{(await response.text())[:8000]}"
    except Exception:
        body_text = url
    return _extract_image_id_from_text(body_text)


_URL_CACHE: Dict[str, tuple[str, float]] = {}
URL_CACHE_TTL_SEC = 600.0
FAST_URL_ONLY = True


def _cache_get(image_url: str) -> Optional[str]:
    cached = _URL_CACHE.get(image_url)
    if not cached:
        return None
    search_url, cached_at = cached
    if time.monotonic() - cached_at > URL_CACHE_TTL_SEC:
        _URL_CACHE.pop(image_url, None)
        return None
    return search_url


def _cache_set(image_url: str, search_url: str) -> None:
    if image_url and search_url:
        _URL_CACHE[image_url] = (search_url, time.monotonic())


def clear_url_cache() -> None:
    _URL_CACHE.clear()


def _is_1688_host(url: str) -> bool:
    return "1688.com" in str(url or "")


async def _page_has_upload_input(page: Page) -> bool:
    try:
        return await page.locator('input[type="file"]').count() > 0
    except Exception:
        return False


_CAPTCHA_MARKERS = ("unusual traffic", "밀어서 확인", "滑动验证", "nc-container")
_UPLOAD_ENTRY_URLS = (
    "https://www.1688.com/",
    "https://s.1688.com/youyuan/index.htm",
)


async def _page_has_captcha(page: Page) -> bool:
    try:
        body = await page.evaluate("() => (document.body && document.body.innerText) || ''")
    except Exception:
        return False
    lowered = str(body).lower()
    return any(marker.lower() in lowered for marker in _CAPTCHA_MARKERS)


async def _wait_for_file_input(page: Page, *, timeout_ms: int) -> Any:
    file_input = page.locator('input[type="file"]')
    deadline = time.monotonic() + (timeout_ms / 1000)
    warned_captcha = False
    while time.monotonic() < deadline:
        if await file_input.count() > 0:
            return file_input.first
        if not warned_captcha and await _page_has_captcha(page):
            warned_captcha = True
        await asyncio.sleep(0.8)
    if warned_captcha:
        raise RuntimeError("captcha_not_cleared")
    raise RuntimeError("file input not found on 1688 home")


async def _upload_image_and_capture_id(
    page: Page,
    image_bytes: bytes,
    *,
    navigation_timeout_ms: int,
    home_sleep_sec: float = 1.0,
    image_id_wait_sec: float = 12.0,
    file_input_timeout_ms: Optional[int] = None,
    reuse_home: bool = False,
    fast: bool = False,
) -> tuple[Optional[str], str]:
    captured_image_ids: List[str] = []
    upload_started = False
    poll_sec = 0.1 if fast else 0.3

    async def _on_response(response: Any) -> None:
        image_id = await _capture_image_id_from_response(response, upload_started=upload_started)
        if image_id:
            captured_image_ids.append(image_id)

    page.on("response", _on_response)
    try:
        file_input_timeout_ms = file_input_timeout_ms or min(45000, navigation_timeout_ms)
        file_input = None
        last_error = "file input not found on 1688 home"

        if reuse_home and _is_1688_host(page.url) and await _page_has_upload_input(page):
            file_input = page.locator('input[type="file"]').first
        else:
            for entry_url in _UPLOAD_ENTRY_URLS:
                await page.goto(entry_url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
                if home_sleep_sec > 0:
                    await asyncio.sleep(home_sleep_sec)
                try:
                    file_input = await _wait_for_file_input(
                        page,
                        timeout_ms=file_input_timeout_ms,
                    )
                    last_error = ""
                    break
                except RuntimeError as exc:
                    last_error = str(exc)
                    continue
            else:
                raise RuntimeError(last_error)

        upload_started = True
        await file_input.set_input_files(
            {
                "name": "coupang-query.jpg",
                "mimeType": "image/jpeg",
                "buffer": image_bytes,
            }
        )
        upload_ready_timeout = min(15000 if fast else 15000, navigation_timeout_ms)
        await _wait_for_home_upload_ready(page, timeout_ms=upload_ready_timeout, fast=fast)

        deadline = time.monotonic() + image_id_wait_sec
        while time.monotonic() < deadline and not captured_image_ids:
            await asyncio.sleep(poll_sec)

        image_id = captured_image_ids[-1] if captured_image_ids else None
        if not image_id:
            image_id = await _extract_image_id_from_page(page)
        return (image_id, page.url)
    finally:
        page.remove_listener("response", _on_response)


async def search_1688_image_search_url_only(
    page: Page,
    image_url: str,
    *,
    navigation_timeout_ms: int,
    fetch_source: str = "browser_upload_url_only",
    reuse_home: bool = False,
    use_cache: bool = True,
    fast: bool = FAST_URL_ONLY,
) -> ChinaSearchResult:
    image_url = str(image_url or "").strip()
    if not image_url:
        return ChinaSearchResult(status="NO_IMAGE", image_url="", error="empty image_url")

    if use_cache:
        cached_url = _cache_get(image_url)
        if cached_url:
            image_id = _extract_image_id_from_text(cached_url) or ""
            search_url = (
                _build_image_search_url(image_id, source_image_url=image_url)
                if image_id
                else cached_url
            )
            return ChinaSearchResult(
                status="URL_OK",
                image_url=image_url,
                search_url=search_url,
                fetch_source=f"{fetch_source}_cache",
                image_id=image_id,
            )

    try:
        image_bytes = await _download_image_bytes(image_url)
    except Exception as exc:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error=f"image_download_{type(exc).__name__}: {exc}",
            fetch_source=fetch_source,
        )

    home_sleep = 0.4 if fast else 0.8
    image_id_wait = 18.0 if fast else 12.0

    upload_attempts: list[tuple[bool, bool]] = [(reuse_home, fast)]
    if reuse_home:
        upload_attempts.append((False, fast))
    upload_attempts.append((False, False))

    image_id: Optional[str] = None
    page_url = page.url
    last_upload_error = ""

    for attempt_index, (attempt_reuse_home, attempt_fast) in enumerate(upload_attempts):
        try:
            image_id, page_url = await _upload_image_and_capture_id(
                page,
                image_bytes,
                navigation_timeout_ms=navigation_timeout_ms,
                home_sleep_sec=home_sleep if attempt_fast else 0.8,
                image_id_wait_sec=image_id_wait if attempt_fast else 12.0,
                file_input_timeout_ms=120_000 if fetch_source.startswith("local_kr") else None,
                reuse_home=attempt_reuse_home,
                fast=attempt_fast,
            )
        except Exception as exc:
            last_upload_error = f"upload_{type(exc).__name__}: {exc}"
            if attempt_index + 1 < len(upload_attempts):
                continue
            return ChinaSearchResult(
                status="NO_MATCH",
                image_url=image_url,
                error=last_upload_error,
                search_url=page.url,
                fetch_source=fetch_source,
            )

        if image_id:
            break
        last_upload_error = "image_id_not_captured_after_upload"

    if not image_id:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error=last_upload_error or "image_id_not_captured_after_upload",
            search_url=page_url,
            fetch_source=fetch_source,
        )

    search_url = _build_image_search_url(image_id, source_image_url=image_url)
    if use_cache:
        _cache_set(image_url, search_url)
    return ChinaSearchResult(
        status="URL_OK",
        image_url=image_url,
        search_url=search_url,
        fetch_source=fetch_source,
        image_id=image_id,
    )


async def _search_via_home_upload(
    page: Page,
    context: BrowserContext,
    image_url: str,
    image_bytes: bytes,
    *,
    top_n: int,
    navigation_timeout_ms: int,
) -> ChinaSearchResult:
    del context  # kept for call-site compatibility
    try:
        image_id, page_url = await _upload_image_and_capture_id(
            page,
            image_bytes,
            navigation_timeout_ms=navigation_timeout_ms,
        )
    except Exception as exc:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error=f"upload_{type(exc).__name__}: {exc}",
            search_url=page.url,
            fetch_source="browser_upload",
        )

    if not image_id:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="image_id_not_captured_after_upload",
            search_url=page_url,
            fetch_source="browser_upload",
        )

    target_url = _build_image_search_url(image_id, source_image_url=image_url)
    await page.goto(target_url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
    await asyncio.sleep(2)

    if not _is_image_search_url(page.url):
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error="image_search_navigation_timeout",
            search_url=page.url,
            fetch_source="browser_upload",
            image_id=image_id,
        )

    parsed = await _parse_image_search_page(
        page,
        image_url,
        top_n=top_n,
        fetch_source="browser_upload",
    )
    parsed.image_id = image_id
    if not parsed.search_url:
        parsed.search_url = target_url
    return parsed


async def search_1688_by_image_url(
    page: Page,
    image_url: str,
    *,
    top_n: int,
    navigation_timeout_ms: int,
    settings: Optional[LocalCrawlerSettings] = None,
) -> ChinaSearchResult:
    settings = settings or get_settings()
    image_url = str(image_url or "").strip()
    if not image_url:
        return ChinaSearchResult(status="NO_IMAGE", image_url="", error="empty image_url")

    context = page.context
    last_browser_error = ""

    try:
        image_bytes = await _download_image_bytes(image_url)
    except Exception as exc:
        return ChinaSearchResult(
            status="NO_MATCH",
            image_url=image_url,
            error=f"image_download_{type(exc).__name__}: {exc}",
            fetch_source="browser_upload",
        )

    try:
        home_result = await _search_via_home_upload(
            page,
            context,
            image_url,
            image_bytes,
            top_n=top_n,
            navigation_timeout_ms=navigation_timeout_ms,
        )
        if home_result.status in {"OK", "LOW_CONFIDENCE"}:
            return home_result
        if _is_image_search_url(home_result.search_url):
            return home_result
        if home_result.error in {
            "image_id_not_captured_after_upload",
            "image_search_navigation_timeout",
            "empty_search_results",
            "image_search_no_prices",
        }:
            return home_result
        last_browser_error = home_result.error or "home_upload_failed"
    except Exception as exc:
        last_browser_error = f"home_upload_{type(exc).__name__}: {exc}"

    for search_url in build_image_search_urls(image_url):
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
            await asyncio.sleep(4)
            if _is_image_search_url(page.url):
                result = await _parse_image_search_page(
                    page,
                    image_url,
                    top_n=top_n,
                    fetch_source="browser_youyuan",
                )
                if result.status in {"OK", "LOW_CONFIDENCE", "NO_MATCH"} and result.search_url:
                    return result
            await _scroll_results(page)
            payload = await _extract_offer_cards(page)
            page_url = str(payload.get("pageUrl") or search_url)
            body_preview = str(payload.get("bodyPreview") or "")
            result = _result_from_image_search_page(
                payload=payload,
                image_url=image_url,
                page_url=page_url,
                body_preview=body_preview,
                top_n=top_n,
                fetch_source="browser_youyuan",
            )
            if result.status in {"OK", "LOW_CONFIDENCE"}:
                return result
            last_browser_error = result.error or "youyuan_no_prices"
        except Exception as exc:
            message = str(exc)
            if any(marker in message for marker in _ROBOTS_BLOCKED_MARKERS):
                continue
            last_browser_error = message
        else:
            last_browser_error = last_browser_error or "youyuan_no_prices"

        html = _fetch_html_via_unlocker(search_url, settings=settings)
        if html:
            unlocker_result = _result_from_html(
                html=html,
                image_url=image_url,
                search_url=search_url,
                fetch_source="unlocker",
                top_n=top_n,
            )
            if unlocker_result.status == "OK":
                return unlocker_result

    return ChinaSearchResult(
        status="NO_MATCH",
        image_url=image_url,
        error=last_browser_error or "image_search_failed",
        search_url=page.url,
        fetch_source="browser_upload",
    )


async def connect_browser(playwright: Any, ws_endpoint: str) -> Browser:
    return await playwright.chromium.connect_over_cdp(ws_endpoint)


async def launch_local_browser(
    playwright: Any,
    *,
    headless: bool,
) -> Browser:
    try:
        return await playwright.chromium.launch(headless=headless, channel="chrome")
    except Exception:
        return await playwright.chromium.launch(headless=headless)


def _merge_row_with_china_result(
    row: Dict[str, Any],
    result: ChinaSearchResult,
    *,
    fx_rate: float,
    url_only: bool,
) -> Dict[str, Any]:
    merged = dict(row)
    merged["china_search_status"] = result.status
    merged["china_search_url"] = result.search_url
    merged["china_search_error"] = result.error
    merged["china_fetch_source"] = result.fetch_source
    if result.image_id:
        merged["china_image_id"] = result.image_id

    if url_only:
        return merged

    merged["china_match_count"] = result.match_count
    merged["china_avg_price_cny"] = result.avg_price_cny
    merged["china_avg_price_krw"] = (
        round(result.avg_price_cny * fx_rate, 0) if result.avg_price_cny is not None else None
    )
    merged["china_prices_cny"] = result.prices_cny
    merged["china_sample_titles"] = result.sample_titles
    if merged.get("price") and merged.get("china_avg_price_krw"):
        try:
            coupang_price = float(merged["price"])
            china_krw = float(merged["china_avg_price_krw"])
            if coupang_price > 0:
                merged["margin_pct_est"] = round(
                    (coupang_price - china_krw) / coupang_price * 100, 1
                )
        except (TypeError, ValueError):
            pass
    return merged


async def _run_batch_with_browser(
    rows: List[Dict[str, Any]],
    *,
    settings: LocalCrawlerSettings,
    browser_factory: Any,
    process_row: Any,
    sleep_seconds: float,
    url_only: bool,
) -> List[Dict[str, Any]]:
    fx_rate = float(settings.china_fx_cny_to_krw or 185.0)
    timeout_ms = int(settings.crawler_navigation_timeout_ms or 120_000)
    updated: List[Dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await browser_factory(playwright)
        try:
            page = await browser.new_page()
            page.set_default_timeout(timeout_ms)
            for index, row in enumerate(rows, start=1):
                result = await process_row(page, row, timeout_ms=timeout_ms, settings=settings)
                updated.append(
                    _merge_row_with_china_result(
                        row,
                        result,
                        fx_rate=fx_rate,
                        url_only=url_only,
                    )
                )
                if index < len(rows):
                    await asyncio.sleep(sleep_seconds)
        finally:
            await browser.close()

    return updated


async def run_batch_image_search_url_only(
    items: List[Dict[str, Any]],
    *,
    settings: Optional[LocalCrawlerSettings] = None,
    limit: Optional[int] = None,
    sleep_seconds: float = 1.0,
    browser_mode: str = "local_kr",
    headless: bool = False,
) -> List[Dict[str, Any]]:
    settings = settings or get_settings()
    rows = list(items)
    if limit is not None and limit > 0:
        rows = rows[:limit]

    fetch_source = "local_kr_url_only" if browser_mode == "local_kr" else "browser_upload_url_only"

    async def process_row(page: Page, row: Dict[str, Any], *, timeout_ms: int, settings: Any) -> ChinaSearchResult:
        del settings
        image_url = str(row.get("image_url") or "").strip()
        return await search_1688_image_search_url_only(
            page,
            image_url,
            navigation_timeout_ms=timeout_ms,
            fetch_source=fetch_source,
        )

    if browser_mode == "local_kr":

        async def browser_factory(playwright: Any) -> Browser:
            return await launch_local_browser(playwright, headless=headless)

    elif browser_mode == "brightdata":
        ws = (settings.brightdata_browser_ws_1688 or "").strip()
        if not ws:
            raise RuntimeError("BRIGHTDATA_BROWSER_WS_1688 is not configured")

        async def browser_factory(playwright: Any) -> Browser:
            return await connect_browser(playwright, ws)

    else:
        raise ValueError(f"unsupported browser_mode: {browser_mode}")

    return await _run_batch_with_browser(
        rows,
        settings=settings,
        browser_factory=browser_factory,
        process_row=process_row,
        sleep_seconds=sleep_seconds,
        url_only=True,
    )


async def run_batch_image_search(
    items: List[Dict[str, Any]],
    *,
    settings: Optional[LocalCrawlerSettings] = None,
    limit: Optional[int] = None,
    sleep_seconds: float = 3.0,
) -> List[Dict[str, Any]]:
    settings = settings or get_settings()
    ws = (settings.brightdata_browser_ws_1688 or "").strip()
    if not ws:
        raise RuntimeError("BRIGHTDATA_BROWSER_WS_1688 is not configured")

    top_n = int(settings.china_search_top_n or 8)
    rows = list(items)
    if limit is not None and limit > 0:
        rows = rows[:limit]

    async def process_row(page: Page, row: Dict[str, Any], *, timeout_ms: int, settings: Any) -> ChinaSearchResult:
        image_url = str(row.get("image_url") or "").strip()
        return await search_1688_by_image_url(
            page,
            image_url,
            top_n=top_n,
            navigation_timeout_ms=timeout_ms,
            settings=settings,
        )

    async def browser_factory(playwright: Any) -> Browser:
        return await connect_browser(playwright, ws)

    return await _run_batch_with_browser(
        rows,
        settings=settings,
        browser_factory=browser_factory,
        process_row=process_row,
        sleep_seconds=sleep_seconds,
        url_only=False,
    )


@dataclass
class Warm1688UrlSession:
    """Keep Bright Data browser open and reuse 1688 home for faster URL generation."""

    ws_endpoint: str = ""
    navigation_timeout_ms: int = 120_000
    _playwright: Any = field(default=None, repr=False)
    _browser: Optional[Browser] = field(default=None, repr=False)
    _page: Optional[Page] = field(default=None, repr=False)
    _request_count: int = 0

    async def open(self) -> None:
        ws = (self.ws_endpoint or "").strip()
        if not ws:
            raise RuntimeError("ws_endpoint is required")
        self._playwright = await async_playwright().start()
        self._browser = await connect_browser(self._playwright, ws)
        self._page = await self._browser.new_page()
        self._page.set_default_timeout(self.navigation_timeout_ms)

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    async def generate_url(
        self,
        image_url: str,
        *,
        reuse_home: bool = True,
        use_cache: bool = True,
        fast: bool = FAST_URL_ONLY,
    ) -> ChinaSearchResult:
        if self._page is None:
            raise RuntimeError("Warm1688UrlSession is not open")
        self._request_count += 1
        reuse = reuse_home and self._request_count > 1
        return await search_1688_image_search_url_only(
            self._page,
            image_url,
            navigation_timeout_ms=self.navigation_timeout_ms,
            fetch_source="browser_upload_url_only_warm",
            reuse_home=reuse,
            use_cache=use_cache,
            fast=fast,
        )
