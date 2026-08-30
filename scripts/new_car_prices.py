"""
New car MSRP scraper — fetches official pricing from manufacturer websites.

All major car manufacturer sites block standard HTTP requests (403 Forbidden).
This script uses Playwright stealth mode to bypass bot detection and extract
official MSRP, trim levels, and feature availability.

Supported manufacturers: toyota, lexus, honda, hyundai, kia, ford, chevrolet

Usage:
    python3 scripts/new_car_prices.py --make toyota --model sienna
    python3 scripts/new_car_prices.py --make lexus --model tx
    python3 scripts/new_car_prices.py --make honda --model odyssey
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from rich.console import Console

# Add parent to path so we can import from scrapers/
sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers.base import UA

console = Console()

# Official manufacturer URLs — all block standard HTTP requests
MANUFACTURER_URLS = {
    "toyota": {
        "sienna":            "https://www.toyota.com/sienna",
        "camry":             "https://www.toyota.com/camry",
        "rav4":              "https://www.toyota.com/rav4",
        "highlander":        "https://www.toyota.com/highlander",
        "grand highlander":  "https://www.toyota.com/grandhighlander",
        "corolla":           "https://www.toyota.com/corolla",
        "4runner":           "https://www.toyota.com/4runner",
        "tacoma":            "https://www.toyota.com/tacoma",
        "tundra":            "https://www.toyota.com/tundra",
        "prius":             "https://www.toyota.com/prius",
    },
    "lexus": {
        "tx":   "https://www.lexus.com/models/TX",
        "rx":   "https://www.lexus.com/models/RX",
        "nx":   "https://www.lexus.com/models/NX",
        "es":   "https://www.lexus.com/models/ES",
        "gx":   "https://www.lexus.com/models/GX",
        "lx":   "https://www.lexus.com/models/LX",
    },
    "honda": {
        "odyssey":   "https://www.honda.com/odyssey",
        "crv":       "https://www.honda.com/cr-v",
        "pilot":     "https://www.honda.com/pilot",
        "accord":    "https://www.honda.com/accord",
        "civic":     "https://www.honda.com/civic",
    },
    "hyundai": {
        "tucson":   "https://www.hyundaiusa.com/us/en/vehicles/tucson",
        "santa fe": "https://www.hyundaiusa.com/us/en/vehicles/santa-fe",
        "palisade": "https://www.hyundaiusa.com/us/en/vehicles/palisade",
    },
    "ford": {
        "explorer":  "https://www.ford.com/suvs/explorer",
        "f-150":     "https://www.ford.com/trucks/f150",
        "maverick":  "https://www.ford.com/trucks/maverick",
        "bronco":    "https://www.ford.com/suvs/bronco",
    },
    "chevrolet": {
        "equinox":  "https://www.chevrolet.com/suvs/equinox",
        "traverse": "https://www.chevrolet.com/suvs/traverse",
        "tahoe":    "https://www.chevrolet.com/suvs/tahoe",
        "silverado": "https://www.chevrolet.com/trucks/silverado",
    },
}

# Keywords to extract from manufacturer pages
PRICE_KEYWORDS = [
    "$", "msrp", "starting", "as low as", "from",
    "xle", "le ", "limited", "platinum", "touring", "sport", "premium",
    "awd", "4wd", "fwd", "hybrid", "phev", "ev",
]
FEATURE_KEYWORDS = [
    "360", "panoramic", "parking assist", "blind spot", "lane",
    "sunroof", "moonroof", "wireless", "heated", "ventilated",
    "driver assist", "safety", "camera", "navigation", "apple carplay",
]


async def scrape_manufacturer(make: str, model: str, url: str) -> dict:
    """Scrape official manufacturer URL for MSRP and trim data."""
    console.print(f"\n[bold cyan]{'═'*60}[/bold cyan]")
    console.print(f"[bold]🏭 {make.upper()} {model.upper()} — Official MSRP[/bold]")
    console.print(f"[dim]{url}[/dim]")
    console.print(f"[bold cyan]{'═'*60}[/bold cyan]")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()
        await Stealth(navigator_webdriver=False).apply_stealth_async(page)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(4)
            text = await page.inner_text("body")
        except Exception as e:
            console.print(f"[red]Error fetching {url}: {e}[/red]")
            await browser.close()
            return {"make": make, "model": model, "url": url, "prices": [], "features": []}
        finally:
            await browser.close()

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    prices = [l for l in lines if any(k.lower() in l.lower() for k in PRICE_KEYWORDS)][:40]
    features = [l for l in lines if any(k.lower() in l.lower() for k in FEATURE_KEYWORDS)][:30]

    if prices:
        console.print("\n[bold green]Pricing & Trims:[/bold green]")
        for p in prices[:20]:
            console.print(f"  {p}")
    else:
        console.print("[yellow]No pricing data extracted — site may have changed structure[/yellow]")

    if features:
        console.print("\n[bold green]Features Found:[/bold green]")
        for f in features[:15]:
            console.print(f"  {f}")

    return {
        "make": make,
        "model": model,
        "url": url,
        "prices": prices,
        "features": features,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch official new car MSRP from manufacturer websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/new_car_prices.py --make toyota --model sienna
  python3 scripts/new_car_prices.py --make lexus --model tx
  python3 scripts/new_car_prices.py --make honda --model odyssey
  python3 scripts/new_car_prices.py --list-models toyota
        """,
    )
    parser.add_argument("--make", help="Manufacturer (toyota, lexus, honda, hyundai, ford, chevrolet)")
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--list-models", metavar="MAKE", help="List available models for a manufacturer")
    parser.add_argument("--save", action="store_true", help="Save results to output/ as JSON")
    args = parser.parse_args()

    if args.list_models:
        make = args.list_models.lower()
        models = MANUFACTURER_URLS.get(make, {})
        if models:
            console.print(f"\nSupported {make.upper()} models:")
            for m in models:
                console.print(f"  {m}")
        else:
            console.print(f"[yellow]No models found for '{make}'. Supported: {list(MANUFACTURER_URLS.keys())}[/yellow]")
        return

    if not args.make or not args.model:
        parser.print_help()
        return

    make = args.make.lower()
    model = args.model.lower()

    make_models = MANUFACTURER_URLS.get(make)
    if not make_models:
        console.print(f"[red]Unsupported manufacturer: {make}[/red]")
        console.print(f"Supported: {list(MANUFACTURER_URLS.keys())}")
        return

    url = make_models.get(model)
    if not url:
        console.print(f"[red]Model '{model}' not found for {make}[/red]")
        console.print(f"Available: {list(make_models.keys())}")
        return

    result = asyncio.run(scrape_manufacturer(make, model, url))

    if args.save:
        import os
        os.makedirs("output", exist_ok=True)
        fname = f"output/new_{make}_{model.replace(' ', '_')}_msrp.json"
        with open(fname, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"\n[dim]Saved: {fname}[/dim]")


if __name__ == "__main__":
    main()
