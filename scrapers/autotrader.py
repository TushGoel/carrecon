"""AutoTrader used car scraper with stealth Playwright."""
import asyncio

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from .base import BaseScraper, UA


class AutoTraderScraper(BaseScraper):
    BASE = "https://www.autotrader.com"

    def build_url(self, make: str, model: str, zip_code: str,
                  year_min: int = None, year_max: int = None,
                  max_price: int = None, max_miles: int = 80000) -> str:
        """Build an AutoTrader search URL for used listings."""
        make_upper = make.upper()
        model_upper = "_".join(model.upper().split())
        url = (
            f"{self.BASE}/cars-for-sale/used-cars/{make_upper}/{model_upper}"
            f"?zip={zip_code}&searchRadius=500&mileage=0-{max_miles}"
            f"&sortBy=price-asc&numRecords=25"
        )
        if year_min:
            url += f"&startYear={year_min}"
        if year_max:
            url += f"&endYear={year_max}"
        if max_price:
            url += f"&maxPrice={max_price}"
        return url

    async def scrape(self, make: str, model: str, zip_code: str,
                     year_min: int = None, year_max: int = None,
                     max_price: int = None, max_miles: int = 80000,
                     retries: int = 2) -> list[str]:
        """Scrape AutoTrader for used listings. Retries on failure."""
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
                keywords = ["$", "price", "deal", "miles", "2020", "2021",
                            "2022", "2023", "2024", "2025", "great", "good", "fair"]
                return [l for l in lines if any(k.lower() in l.lower() for k in keywords)]

            except Exception as e:
                if attempt == retries:
                    print(f"  AutoTrader failed after {retries} attempts: {e}")
                    return []
                await asyncio.sleep(2 ** attempt)
        return []
