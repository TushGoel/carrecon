"""CarMax used car scraper with stealth Playwright."""
import asyncio

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from .base import BaseScraper, UA


class CarMaxScraper(BaseScraper):
    BASE = "https://www.carmax.com"

    def build_url(self, make: str, model: str, zip_code: str,
                  year_min: int = None, year_max: int = None,
                  max_price: int = None, max_miles: int = 80000) -> str:
        """Build a CarMax search URL for used listings."""
        model_slug = model.lower().replace(" ", "-")
        make_slug = make.lower()
        url = (
            f"{self.BASE}/cars/{make_slug}/{model_slug}"
            f"?zip={zip_code}&miles=0-{max_miles}&sortby=price-asc"
        )
        if year_min:
            url += f"&year={year_min}-2026"
        if max_price:
            url += f"&price=0-{max_price}"
        return url

    async def scrape(self, make: str, model: str, zip_code: str,
                     year_min: int = None, year_max: int = None,
                     max_price: int = None, max_miles: int = 80000,
                     retries: int = 2) -> list[str]:
        """Scrape CarMax for used listings. Retries on failure."""
        url = self.build_url(make, model, zip_code, year_min, year_max,
                             max_price, max_miles)
        for attempt in range(1, retries + 1):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=self.headless)
                    page = await self.new_page(browser)
                    await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                    await asyncio.sleep(5)
                    text = await page.inner_text("body")
                    await browser.close()

                lines = [l.strip() for l in text.split("\n") if l.strip()]
                keywords = ["$", "price", "miles", "2020", "2021",
                            "2022", "2023", "2024", "2025", "transfer", "available"]
                return [l for l in lines if any(k.lower() in l.lower() for k in keywords)]

            except Exception as e:
                if attempt == retries:
                    print(f"  CarMax failed after {retries} attempts: {e}")
                    return []
                await asyncio.sleep(2 ** attempt)
        return []
