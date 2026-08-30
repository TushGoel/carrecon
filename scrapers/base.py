"""Base scraper class with stealth Playwright setup."""
import asyncio
import json
from datetime import datetime

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


class BaseScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def new_page(self, browser):
        """Create a new stealth browser page."""
        ctx = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()
        await Stealth(navigator_webdriver=False).apply_stealth_async(page)
        return page

    def save(self, data: dict, name: str) -> str:
        """Save results to data/ as JSON."""
        import os
        os.makedirs("data", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        path = f"data/{name}_{ts}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path
