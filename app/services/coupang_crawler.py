from __future__ import annotations

import asyncio
import random
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from app.core.config import Settings
from app.services.r2_storage import R2StorageService


class CoupangCrawlerService:
    SEARCH_URL = "https://www.coupang.com/np/search"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.r2_service = R2StorageService(settings)
        self.stealth = Stealth(
            navigator_languages_override=("ko-KR", "ko"),
            navigator_platform_override="Win32",
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.brightdata_browser_ws)

    async def crawl_keywords(self, keywords: List[str]) -> Dict[str, Any]:
        if not self.is_configured:
            raise RuntimeError("BRIGHTDATA_BROWSER_WS is not configured.")

        sanitized_keywords = [str(keyword or "").strip() for keyword in keywords if str(keyword or "").strip()]
        keyword_results: List[Dict[str, Any]] = []

        for keyword in sanitized_keywords[:10]:
            result = await self._crawl_single_keyword(keyword)
            keyword_results.append(result)
            await self._human_pause()

        payload = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "keyword_count": len(keyword_results),
            "keywords": keyword_results,
        }
        key = self.r2_service.save_json_bytes(
            key=f"coupang/test/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json",
            payload=payload,
        )
        return {
            "keyword_count": len(keyword_results),
            "items": keyword_results,
            "r2_key": key,
        }

    async def _crawl_single_keyword(self, keyword: str) -> Dict[str, Any]:
        browser: Optional[Browser] = None
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(
                    str(self.settings.brightdata_browser_ws)
                )
                context = browser.contexts[0] if browser.contexts else await browser.new_context(
                    locale="ko-KR",
                    timezone_id="Asia/Seoul",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()
                await self.stealth.apply_stealth_async(page)
                page.set_default_navigation_timeout(self.settings.brightdata_navigation_timeout)
                page.set_default_timeout(self.settings.brightdata_action_timeout)

                search_url = self._build_search_url(keyword)
                await page.goto(search_url, wait_until="domcontentloaded")
                await self._simulate_human_scroll(page)

                products = await self._extract_search_results(page)
                detailed_products = []
                for product in products[: self.settings.coupang_detail_limit]:
                    detailed_products.append(await self._enrich_product_detail(context, product))

                return {
                    "keyword": keyword,
                    "search_url": search_url,
                    "product_count": len(detailed_products),
                    "products": detailed_products,
                }
        finally:
            try:
                if page is not None:
                    await page.close()
            except Exception:
                pass
            try:
                if context is not None:
                    await context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass

    def _build_search_url(self, keyword: str) -> str:
        query = urllib.parse.quote(keyword)
        return f"{self.SEARCH_URL}?component=&q={query}&channel=user"

    async def _simulate_human_scroll(self, page: Page) -> None:
        steps = random.randint(
            self.settings.coupang_scroll_steps_min,
            self.settings.coupang_scroll_steps_max,
        )
        for _ in range(steps):
            await page.mouse.wheel(0, random.randint(500, 1200))
            await asyncio.sleep(random.uniform(0.6, 1.4))

    async def _extract_search_results(self, page: Page) -> List[Dict[str, Any]]:
        await page.wait_for_selector("ul.search-product-list li.search-product", timeout=30000)
        cards = await page.query_selector_all("ul.search-product-list li.search-product")
        products: List[Dict[str, Any]] = []

        for card in cards:
            classes = (await card.get_attribute("class")) or ""
            if "search-product__ad" in classes or "Ad" in classes:
                continue

            link = await card.query_selector("a.search-product-link")
            name_node = await card.query_selector(".name")
            price_whole = await card.query_selector(".price-value")
            rating_node = await card.query_selector(".rating")
            review_node = await card.query_selector(".rating-total-count")
            badge_nodes = await card.query_selector_all(".badge")

            name = (await name_node.inner_text()) if name_node else ""
            if not name:
                continue

            href = await link.get_attribute("href") if link else None
            product_url = f"https://www.coupang.com{href}" if href and href.startswith("/") else (href or "")
            price = (await price_whole.inner_text()) if price_whole else ""
            rating = (await rating_node.inner_text()) if rating_node else ""
            review_count = (await review_node.inner_text()) if review_node else ""
            badges = [(await badge.inner_text()).strip() for badge in badge_nodes]
            delivery_type = self._resolve_delivery_type(badges)

            products.append(
                {
                    "title": name.strip(),
                    "price": price.strip(),
                    "rating": rating.strip(),
                    "review_count": review_count.strip("() ").strip(),
                    "delivery_type": delivery_type,
                    "product_url": product_url,
                }
            )
            if len(products) >= self.settings.coupang_result_limit:
                break

        return products

    async def _enrich_product_detail(self, context: BrowserContext, product: Dict[str, Any]) -> Dict[str, Any]:
        detail_page = await context.new_page()
        await self.stealth.apply_stealth_async(detail_page)
        detail_page.set_default_navigation_timeout(self.settings.brightdata_navigation_timeout)
        detail_page.set_default_timeout(self.settings.brightdata_action_timeout)
        seller = ""
        monthly_sales = ""
        delivery_fee = ""

        try:
            if product.get("product_url"):
                await detail_page.goto(str(product["product_url"]), wait_until="domcontentloaded")
                await asyncio.sleep(random.uniform(0.8, 1.6))
                seller = await self._safe_text(
                    detail_page,
                    [
                        ".prod-sale-vendor-name",
                        ".seller-name",
                        ".prod-sale-vendor",
                    ],
                )
                monthly_sales = await self._safe_text(
                    detail_page,
                    [
                        ".prod-sales-volume",
                        ".shipping-fee-title + span",
                    ],
                )
                delivery_fee = await self._safe_text(
                    detail_page,
                    [
                        ".delivery-fee",
                        ".prod-shipping-fee-message",
                        ".shipping-fee-title + span",
                    ],
                )
        finally:
            await detail_page.close()

        enriched = dict(product)
        enriched.update(
            {
                "seller_name": seller,
                "monthly_sales": monthly_sales,
                "delivery_fee": delivery_fee,
            }
        )
        return enriched

    async def _safe_text(self, page: Page, selectors: List[str]) -> str:
        for selector in selectors:
            node = await page.query_selector(selector)
            if node:
                text = (await node.inner_text()).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def _resolve_delivery_type(badges: List[str]) -> str:
        joined = " ".join(badges)
        if "로켓배송" in joined:
            return "로켓"
        if "로켓직구" in joined or "로켓그로스" in joined:
            return "그로스"
        return "일반"

    async def _human_pause(self) -> None:
        await asyncio.sleep(
            random.uniform(
                float(self.settings.coupang_sleep_min_seconds),
                float(self.settings.coupang_sleep_max_seconds),
            )
        )
