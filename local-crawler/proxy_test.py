import asyncio
import json

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from config import get_settings


async def main() -> None:
    settings = get_settings()
    stealth = Stealth(
        navigator_languages_override=("ko-KR", "ko"),
        navigator_platform_override="Win32",
    )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=settings.crawler_headless,
        )
        context = await browser.new_context(
            locale="ko-KR",
            ignore_https_errors=True,
        )
        page = await context.new_page()
        await stealth.apply_stealth_async(page)
        page.set_default_navigation_timeout(settings.crawler_navigation_timeout_ms)
        page.set_default_timeout(settings.crawler_action_timeout_ms)
        await page.goto("https://ipinfo.io/json", wait_until="domcontentloaded")
        body = await page.locator("body").inner_text()
        print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
