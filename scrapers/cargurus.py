"""CarGurus used car scraper with stealth Playwright."""
import asyncio
import re

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from .base import BaseScraper, UA


# Known CarGurus model IDs — more reliable than guessing slugs.
# CarGurus uses internal IDs (e.g. d551) in their listing URLs.
# Fallback to slug construction for unknown models.
CARGURUS_MODEL_IDS = {
    ("toyota", "sienna"):           "d551",
    ("toyota", "camry"):            "d2246",
    ("toyota", "rav4"):             "d2268",
    ("toyota", "highlander"):       "d2247",
    ("toyota", "grand highlander"): "d2489",
    ("toyota", "4runner"):          "d2240",
    ("toyota", "tacoma"):           "d2257",
    ("toyota", "prius"):            "d2264",
    ("lexus", "tx"):                "d2590",
    ("lexus", "rx"):                "d2285",
    ("lexus", "nx"):                "d2283",
    ("honda", "odyssey"):           "d2112",
    ("honda", "pilot"):             "d2115",
    ("honda", "cr-v"):              "d2089",
    ("honda", "accord"):            "d2082",
    ("hyundai", "palisade"):        "d2388",
    ("hyundai", "santa fe"):        "d2321",
    ("ford", "explorer"):           "d2068",
    ("ford", "f-150"):              "d2070",
}


class CarGurusScraper(BaseScraper):
    BASE = "https://www.cargurus.com"

    def build_url(self, make: str, model: str, zip_code: str,
                  year_min: int = None, year_max: int = None,
                  awd: bool = False, hybrid: bool = False,
                  max_price: int = None) -> str:
        """Build a CarGurus search URL. Uses known model IDs when available,
        falls back to slug construction for unknown models."""
        key = (make.lower(), model.lower())
        model_id = CARGURUS_MODEL_IDS.get(key)

        make_cap = make.capitalize()
        model_cap = "-".join(w.capitalize() for w in model.replace("-", " ").split())
        slug_id = model_id or "d0"
        url = f"{self.BASE}/Cars/new/nl-Used-{make_cap}-{model_cap}-{slug_id}?zip={zip_code}&distance=300"
        if year_min:
            url += f"&minYear={year_min}"
        if year_max:
            url += f"&maxYear={year_max}"
        if max_price:
            url += f"&maxPrice={max_price}"
        if awd:
            url += "&driveType=AWD"
        if hybrid:
            url += "&fuelType=HYBRID"
        return url

    async def scrape(self, make: str, model: str, zip_code: str,
                     year_min: int = None, year_max: int = None,
                     awd: bool = False, hybrid: bool = False,
                     max_price: int = None, retries: int = 2) -> list[str]:
        """Scrape CarGurus for used listings. Retries on failure."""
        url = self.build_url(make, model, zip_code, year_min, year_max,
                             awd, hybrid, max_price)
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
                keywords = ["$", "price", "avg", "fair", "good deal", "miles", "year"]
                return [l for l in lines if any(k in l.lower() for k in keywords)]

            except Exception as e:
                if attempt == retries:
                    print(f"  CarGurus failed after {retries} attempts: {e}")
                    return []
                await asyncio.sleep(2 ** attempt)  # exponential backoff
        return []
