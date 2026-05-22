import asyncio
import json
import random
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, Error as PlaywrightError, Page, async_playwright
from playwright_stealth import Stealth

from config import LocalCrawlerSettings, get_settings
from railway_client import RailwayKeywordClient


OUTPUT_DIR = Path("output")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "max-age=0",
    "pragma": "no-cache",
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}


def _build_search_url(keyword: str) -> str:
    return (
        "https://www.coupang.com/np/search"
        f"?component=&q={urllib.parse.quote(keyword)}&channel=user"
    )


async def _simulate_human_scroll(page: Page, settings: LocalCrawlerSettings) -> None:
    steps = random.randint(settings.crawler_scroll_steps_min, settings.crawler_scroll_steps_max)
    for _ in range(steps):
        await page.mouse.wheel(0, random.randint(500, 1200))
        await asyncio.sleep(random.uniform(0.6, 1.4))


def _normalize_number(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit() or ch in {".", ","}).strip()


def _debug_path(filename: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR / filename


async def _safe_inner_text(node: Any) -> str:
    if node is None:
        return ""
    try:
        return (await node.inner_text()).strip()
    except Exception:
        return ""


async def _extract_price_text(card: Any) -> str:
    candidates = await card.query_selector_all(
        ".PriceArea_priceArea__NntJz .fw-text-[20px]/[24px], "
        ".PriceArea_priceArea__NntJz .Price_priceValue__A4KOr, "
        ".PriceArea_priceArea__NntJz span"
    )
    for candidate in candidates:
        text = await _safe_inner_text(candidate)
        if "원" in text:
            return text
    return ""


async def _extract_review_count_text(card: Any) -> str:
    review_node = await card.query_selector(".ProductRating_productRating__jjf7W")
    if not review_node:
        return ""
    review_text = await _safe_inner_text(review_node)
    if not review_text:
        return ""
    start = review_text.rfind("(")
    end = review_text.rfind(")")
    if start >= 0 and end > start:
        return _normalize_number(review_text[start + 1 : end])
    return _normalize_number(review_text)


async def _extract_rating_text(card: Any) -> str:
    rating_group = await card.query_selector(".ProductRating_productRating__jjf7W [aria-label]")
    if not rating_group:
        return ""
    return ((await rating_group.get_attribute("aria-label")) or "").strip()


async def _save_debug_artifacts(page: Page, prefix: str) -> None:
    html_path = _debug_path(f"{prefix}.html")
    png_path = _debug_path(f"{prefix}.png")
    try:
        html_path.write_text(await page.content(), encoding="utf-8")
    except Exception as exc:
        html_path.write_text(f"debug capture failed: {exc}", encoding="utf-8")
    try:
        await page.screenshot(path=str(png_path), full_page=True)
    except Exception:
        pass


async def _prepare_context(context: Any) -> None:
    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'language', { get: () => 'ko-KR' });
        Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
        """
    )
    await context.set_extra_http_headers(DEFAULT_HEADERS)


async def _warm_up_session(page: Page) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "requested_url": "https://www.coupang.com/",
        "final_url": "",
        "response_status": None,
        "navigation_error": "",
    }
    try:
        response = await page.goto("https://www.coupang.com/", wait_until="domcontentloaded")
        result["response_status"] = response.status if response else None
        result["final_url"] = page.url
        await asyncio.sleep(random.uniform(2.0, 4.0))
        await page.mouse.move(random.randint(200, 500), random.randint(120, 260), steps=random.randint(10, 20))
        await asyncio.sleep(random.uniform(0.8, 1.6))
        await page.mouse.wheel(0, random.randint(200, 700))
        await asyncio.sleep(random.uniform(0.8, 1.6))
        await page.mouse.wheel(0, -random.randint(100, 300))
        await asyncio.sleep(random.uniform(0.8, 1.6))
    except PlaywrightError as exc:
        result["navigation_error"] = str(exc)
        result["final_url"] = page.url
    return result


async def _extract_products(page: Page, settings: LocalCrawlerSettings) -> List[Dict[str, Any]]:
    selectors = [
        '#product-list > li[class*="ProductUnit_productUnit"]',
        '#product-list li[class*="ProductUnit_productUnit"]',
        'li[class*="ProductUnit_productUnit"]',
        'a[href*="/vp/products/"][href*="sourceType=search"]',
    ]
    last_error: Optional[Exception] = None
    cards: List[Any] = []

    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=15000)
            if selector.startswith("a["):
                links = await page.query_selector_all(selector)
                cards = []
                for link in links:
                    card = await link.evaluate_handle(
                        """
                        (node) => node.closest('li') || node.closest('div')
                        """
                    )
                    if card:
                        cards.append(card)
            else:
                cards = await page.query_selector_all(selector)
            if cards:
                break
        except Exception as exc:
            last_error = exc

    if not cards:
        await _save_debug_artifacts(page, "coupang_search_debug")
        if last_error is not None:
            raise last_error
        raise RuntimeError("Coupang product cards not found")

    products: List[Dict[str, Any]] = []

    for card in cards:
        link = await card.query_selector('a[href*="/vp/products/"]')
        href = await link.get_attribute("href") if link else None
        if not href:
            continue
        if "sourceType=search" not in href:
            continue

        name_node = await card.query_selector(".ProductUnit_productNameV2__cV9cw")
        image_node = await card.query_selector("figure.ProductUnit_productImage__Mqcg1 img")
        rank_node = await card.query_selector('[class*="RankMark_rank"]')

        name = await _safe_inner_text(name_node)
        if not name:
            continue

        product_url = f"https://www.coupang.com{href}" if href and href.startswith("/") else (href or "")
        image_url = await image_node.get_attribute("src") if image_node else ""
        price_text = await _extract_price_text(card)
        review_count = await _extract_review_count_text(card)
        rating_text = await _extract_rating_text(card)
        rank_text = await _safe_inner_text(rank_node)

        products.append(
            {
                "title": name,
                "price": price_text,
                "review_count": review_count,
                "rating": rating_text,
                "image_url": image_url or "",
                "product_url": product_url,
                "rank": _normalize_number(rank_text),
            }
        )
        if len(products) >= settings.crawler_result_limit:
            break

    return products


async def _crawl_keyword(browser: Browser, keyword_row: Dict[str, Any], settings: LocalCrawlerSettings, stealth: Stealth) -> Dict[str, Any]:
    context = await browser.new_context(
        locale="ko-KR",
        ignore_https_errors=True,
        user_agent=DEFAULT_USER_AGENT,
        viewport={"width": 1440, "height": 900},
        screen={"width": 1440, "height": 900},
        timezone_id="Asia/Seoul",
        color_scheme="light",
    )
    await _prepare_context(context)
    page = await context.new_page()
    await stealth.apply_stealth_async(page)
    page.set_default_navigation_timeout(settings.crawler_navigation_timeout_ms)
    page.set_default_timeout(settings.crawler_action_timeout_ms)

    try:
        search_url = _build_search_url(keyword_row["keyword"])
        home_result = await _warm_up_session(page)
        await _save_debug_artifacts(page, "coupang_home_last")
        response_status: Optional[int] = None
        navigation_error = ""
        try:
            response = await page.goto(
                search_url,
                wait_until="domcontentloaded",
                referer="https://www.coupang.com/",
            )
            response_status = response.status if response else None
            await asyncio.sleep(random.uniform(1.5, 3.0))
            await _save_debug_artifacts(page, "coupang_search_last")
        except PlaywrightError as exc:
            navigation_error = str(exc)
            response_status = None
            await _save_debug_artifacts(page, "coupang_search_error")
        page_title = await page.title()
        page_content = await page.content()
        lower_title = page_title.lower()
        lower_content = page_content.lower()
        is_blocked = any(
            marker in lower_content
            for marker in (
                "access denied",
                "errors.edgesuite.net",
                "you don't have permission to access",
            )
        ) or "access denied" in lower_title
        return {
            "keyword": keyword_row["keyword"],
            "theme_name": keyword_row.get("theme_name") or "",
            "theme_detail": keyword_row.get("theme_detail") or "",
            "group_name": keyword_row.get("group_name") or "",
            "requested_url": search_url,
            "final_url": page.url,
            "page_title": page_title,
            "is_blocked": is_blocked,
            "html_size": len(page_content),
            "home_requested_url": home_result["requested_url"],
            "home_final_url": home_result["final_url"],
            "home_response_status": home_result["response_status"],
            "home_navigation_error": home_result["navigation_error"],
            "search_response_status": response_status,
            "search_navigation_error": navigation_error,
        }
    finally:
        await page.close()
        await context.close()


async def run_worker() -> Dict[str, Any]:
    settings = get_settings()
    manual_keyword = (settings.manual_keyword or "").strip()
    if manual_keyword:
        keyword_rows = [
            {
                "keyword": manual_keyword,
                "group_name": "manual",
                "theme_name": "",
                "theme_detail": "manual-input",
            }
        ]
    else:
        client = RailwayKeywordClient(settings)
        keyword_rows = client.fetch_keyword_list()
    if not keyword_rows:
        return {
            "status": "empty",
            "message": "수동 키워드와 Railway 키워드 모두 비어 있습니다.",
            "items": [],
        }

    OUTPUT_DIR.mkdir(exist_ok=True)
    stealth = Stealth(
        navigator_languages_override=("ko-KR", "ko"),
        navigator_platform_override="Win32",
    )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=settings.crawler_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--lang=ko-KR",
            ],
        )
        results = []
        try:
            for keyword_row in keyword_rows:
                result = await _crawl_keyword(browser, keyword_row, settings, stealth)
                results.append(result)
                await asyncio.sleep(
                    random.uniform(
                        settings.crawler_sleep_min_seconds,
                        settings.crawler_sleep_max_seconds,
                    )
                )
        finally:
            await browser.close()

    payload = {"status": "ok", "keyword_count": len(results), "items": results}
    output_path = OUTPUT_DIR / "last_crawl.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    payload = asyncio.run(run_worker())
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
