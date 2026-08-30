#!/usr/bin/env python3
"""
Car Research Tool — Fetch used car prices from Cars.com, CarGurus, AutoTrader, and CarMax.

Usage:
    python3 main.py --make toyota --model sienna --zip 10001
    python3 main.py --make honda --model odyssey --zip 10001 --year-min 2022
    python3 main.py --make lexus --model tx --zip 90210 --year-min 2024 --max-price 60000
    python3 main.py --make toyota --model sienna --zip 10001 --format csv
    python3 main.py --make toyota --model sienna --zip 10001 --sources cars cargurus
"""
import argparse
import asyncio
import json
import re
from datetime import datetime

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from rich.console import Console
from rich.table import Table

console = Console()

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


# ── URL builders ──────────────────────────────────────────────────────────────

SUPPORTED_SOURCES = ["cars", "cargurus", "autotrader", "carmax"]


def cars_com_url(make: str, model: str, zip_code: str, year_min: int = None,
                 year_max: int = None, max_price: int = None, max_miles: int = 80000) -> str:
    model_slug = model.lower().replace(" ", "_")
    url = (
        f"https://www.cars.com/shopping/results/"
        f"?makes[]={make.lower()}"
        f"&models[]={make.lower()}-{model_slug}"
        f"&maximum_distance=500"
        f"&mileage_max={max_miles}"
        f"&page_size=20"
        f"&sort=list_price_asc"
        f"&stock_type=used"
        f"&zip={zip_code}"
    )
    if year_min:
        url += f"&year_min={year_min}"
    if year_max:
        url += f"&year_max={year_max}"
    if max_price:
        url += f"&list_price_max={max_price}"
    return url


def cargurus_url(make: str, model: str, zip_code: str, year_min: int = None,
                 year_max: int = None, max_price: int = None) -> str:
    make_cap = make.capitalize()
    model_cap = "-".join(w.capitalize() for w in model.replace("-", " ").split())
    url = (
        f"https://www.cargurus.com/Cars/new/nl-Used-{make_cap}-{model_cap}-d0"
        f"?zip={zip_code}&distance=300"
    )
    if year_min:
        url += f"&minYear={year_min}"
    if year_max:
        url += f"&maxYear={year_max}"
    if max_price:
        url += f"&maxPrice={max_price}"
    return url


# ── Price extraction ──────────────────────────────────────────────────────────

def extract_listings(lines: list[str], source: str) -> list[dict]:
    """Parse raw text lines into structured listing dicts."""
    listings = []
    price_re = re.compile(r"\$[\d,]+")
    year_re = re.compile(r"\b(202[0-9]|201[5-9])\b")
    miles_re = re.compile(r"([\d,]+)\s*(?:mi|miles)", re.IGNORECASE)

    i = 0
    while i < len(lines):
        line = lines[i]
        prices = price_re.findall(line)
        if not prices:
            i += 1
            continue

        # Parse the first price found
        price_str = prices[0].replace("$", "").replace(",", "")
        try:
            price = int(price_str)
        except ValueError:
            i += 1
            continue

        # Skip implausible prices (< $1K or > $200K)
        if price < 1000 or price > 200000:
            i += 1
            continue

        # Look for year in this line and nearby lines
        window = " ".join(lines[max(0, i-2):i+3])
        year_match = year_re.search(window)
        year = int(year_match.group()) if year_match else None

        miles_match = miles_re.search(window)
        miles_raw = miles_match.group(1).replace(",", "") if miles_match else None
        miles = int(miles_raw) if miles_raw else None

        # Deal rating
        deal = None
        for rating in ["Great Deal", "Good Deal", "Fair Deal", "High Price", "Overpriced"]:
            if rating.lower() in window.lower():
                deal = rating
                break

        # Monthly payment
        monthly_re = re.compile(r"\$[\d,]+/mo", re.IGNORECASE)
        monthly_match = monthly_re.search(window)
        monthly = monthly_match.group() if monthly_match else None

        listings.append({
            "price": price,
            "year": year,
            "miles": miles,
            "deal": deal,
            "monthly": monthly,
            "source": source,
        })
        i += 1

    # Deduplicate by price
    seen = set()
    unique = []
    for l in listings:
        if l["price"] not in seen:
            seen.add(l["price"])
            unique.append(l)

    return sorted(unique, key=lambda x: x["price"])[:15]


# ── Scraping ──────────────────────────────────────────────────────────────────

async def _try_schema_org(page) -> list[dict]:
    """Attempt to extract car listings from JSON-LD structured data (schema.org).

    Many sites embed machine-readable data in <script type='application/ld+json'>
    that is far more reliable than regex on inner_text. Try this first.
    """
    try:
        scripts = await page.evaluate("""
            () => Array.from(
                document.querySelectorAll('script[type="application/ld+json"]')
            ).map(s => s.textContent)
        """)
        listings = []
        for raw in scripts:
            try:
                data = json.loads(raw)
                # Flatten @graph arrays
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    t = item.get("@type", "")
                    if "Car" in t or "Vehicle" in t or "Offer" in t:
                        price_raw = (item.get("offers", {}) or {}).get("price") or item.get("price")
                        if price_raw:
                            listings.append({
                                "price": int(float(str(price_raw).replace(",", ""))),
                                "year": item.get("vehicleModelDate") or item.get("modelDate"),
                                "miles": item.get("mileageFromOdometer", {}).get("value") if isinstance(item.get("mileageFromOdometer"), dict) else None,
                                "deal": None,
                                "monthly": None,
                            })
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        return listings
    except Exception:
        return []


async def _try_llm_fallback(raw_text: str, source: str) -> list[dict]:
    """LLM-based extraction fallback when regex returns no results.

    Requires ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable.
    Only called when regex parser returns 0 listings — avoids unnecessary API cost.
    """
    import os
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []

    prompt = f"""Extract used car listings from the following text scraped from {source}.
Return a JSON array. Each object must have: price (integer, USD), year (integer or null),
miles (integer or null), deal (string like "Good Deal" or null).
Only include real car listings, not ads or navigation text.
Return [] if no listings found.

Text:
{raw_text[:3000]}

JSON:"""

    try:
        if os.getenv("ANTHROPIC_API_KEY"):
            import anthropic
            client = anthropic.Anthropic()
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
        else:
            import openai
            client = openai.OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            raw = resp.choices[0].message.content.strip()

        # Extract JSON from response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(raw[start:end])
            return [{**item, "source": source, "monthly": None} for item in items if item.get("price")]
    except Exception:
        pass
    return []


async def scrape_one_source(playwright_instance, url: str, source: str) -> list[str]:
    """Scrape a single source in its own browser context (parallel-safe).

    Each source gets an independent browser context so all four can run
    concurrently via asyncio.gather() without shared page state.
    """
    console.print(f"  → {source}: {url[:85]}...")
    try:
        browser = await playwright_instance.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=UA, viewport={"width": 1440, "height": 900}, locale="en-US"
        )
        page = await ctx.new_page()
        await Stealth(navigator_webdriver=False).apply_stealth_async(page)
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(4)

        # 1. Try schema.org structured data first (most reliable)
        schema_listings = await _try_schema_org(page)
        if schema_listings:
            await browser.close()
            return schema_listings  # return list[dict] directly

        # 2. Fall back to inner_text regex extraction
        text = await page.inner_text("body")
        await browser.close()

        lines = [l.strip() for l in text.split("\n") if l.strip()]
        keywords = ["$", "deal", "avg", "fair", "good", "great", "miles", "mi",
                    "2020", "2021", "2022", "2023", "2024", "2025", "/mo"]
        filtered = [l for l in lines if any(k.lower() in l.lower() for k in keywords)]

        # 3. If regex also finds nothing, try LLM fallback
        parsed = extract_listings(filtered, source)
        if not parsed and filtered:
            llm_results = await _try_llm_fallback(text, source)
            if llm_results:
                return llm_results

        return filtered

    except Exception as e:
        console.print(f"  [red]{source} error: {e}[/red]")
        return []


async def search(make: str, model: str, zip_code: str,
                 year_min: int = None, year_max: int = None,
                 max_price: int = None, max_miles: int = 80000,
                 sources: list = None) -> dict:
    """Search all sources concurrently for used car listings."""
    label = f"{make.upper()} {model.upper()}"
    if year_min or year_max:
        yr = f"{year_min or ''}–{year_max or ''}"
        label += f" ({yr.strip('–')})"

    console.print(f"\n[bold cyan]{'═'*60}[/bold cyan]")
    console.print(f"[bold]🔍 {label} near {zip_code}[/bold]")
    console.print(f"[bold cyan]{'═'*60}[/bold cyan]")

    active = sources or SUPPORTED_SOURCES
    urls = {}
    if "cars" in active:
        urls["Cars.com"] = cars_com_url(make, model, zip_code, year_min, year_max, max_price, max_miles)
    if "cargurus" in active:
        urls["CarGurus"] = cargurus_url(make, model, zip_code, year_min, year_max, max_price)
    if "autotrader" in active:
        from scrapers.autotrader import AutoTraderScraper
        urls["AutoTrader"] = AutoTraderScraper().build_url(make, model, zip_code, year_min, year_max, max_price, max_miles)
    if "carmax" in active:
        from scrapers.carmax import CarMaxScraper
        urls["CarMax"] = CarMaxScraper().build_url(make, model, zip_code, year_min, year_max, max_price, max_miles)

    all_listings = []

    async with async_playwright() as p:
        # ── Parallel scraping: all sources run concurrently ──────────────────
        tasks = [scrape_one_source(p, url, source) for source, url in urls.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (source, _), result in zip(urls.items(), results):
            if isinstance(result, Exception):
                console.print(f"  [red]✗ {source} — {result}[/red]")
                continue
            # result is either list[dict] (schema.org) or list[str] (raw lines)
            if result and isinstance(result[0], dict):
                listings = [{**r, "source": source} for r in result]
            else:
                listings = extract_listings(result or [], source)
            if listings:
                console.print(f"  [green]✅ {source} — {len(listings)} listings[/green]")
                all_listings.extend(listings)
            else:
                console.print(f"  [yellow]⚠️  {source} — no structured listings extracted[/yellow]")

    # Sort all by price, dedupe
    all_listings.sort(key=lambda x: x["price"])
    seen = set()
    unique = []
    for l in all_listings:
        if l["price"] not in seen:
            seen.add(l["price"])
            unique.append(l)

    return {"vehicle": label, "zip": zip_code, "listings": unique}


# ── Display ───────────────────────────────────────────────────────────────────

def display_results(result: dict, fmt: str = "table") -> None:
    """Print results in the requested format: table, json, or csv."""
    listings = result["listings"]
    if not listings:
        console.print(f"[yellow]No listings found for {result['vehicle']}[/yellow]")
        return

    if fmt == "json":
        print(json.dumps(result, indent=2))
        return

    if fmt == "csv":
        import csv, sys
        writer = csv.DictWriter(sys.stdout, fieldnames=["price", "year", "miles", "deal", "monthly", "source"])
        writer.writeheader()
        writer.writerows(listings)
        return

    # Default: rich table
    table = Table(title=f"{result['vehicle']} — near {result['zip']}", show_lines=True)
    table.add_column("Price", style="green bold", justify="right")
    table.add_column("Year", justify="center")
    table.add_column("Miles", justify="right")
    table.add_column("Deal", justify="center")
    table.add_column("Monthly", justify="right")
    table.add_column("Source", style="dim")

    DEAL_COLORS = {"Great Deal": "[green]", "Good Deal": "[green]",
                   "Fair Deal": "[yellow]", "High Price": "[red]", "Overpriced": "[red]"}

    for l in listings:
        deal = l["deal"] or "—"
        color = DEAL_COLORS.get(l["deal"], "")
        table.add_row(
            f"${l['price']:,}",
            str(l["year"]) if l["year"] else "—",
            f"{l['miles']:,}" if l["miles"] else "—",
            f"{color}{deal}[/]" if color else deal,
            l["monthly"] or "—",
            l["source"],
        )

    console.print(table)
    prices = [l["price"] for l in listings]
    console.print(f"\n  [bold]Range:[/bold]   ${min(prices):,} – ${max(prices):,}")
    console.print(f"  [bold]Median:[/bold]  ${sorted(prices)[len(prices)//2]:,}")
    console.print(f"  [bold]Sources:[/bold] {', '.join(sorted(set(l['source'] for l in listings)))}")
    console.print(f"  [bold]Listings:[/bold] {len(listings)}")


# ── Guided wizard ─────────────────────────────────────────────────────────────

def _prompt(label: str, hint: str = "", default: str = "") -> str:
    """Prompt user for input with optional hint and default."""
    hint_str = f" [dim]{hint}[/dim]" if hint else ""
    default_str = f" [dim](default: {default})[/dim]" if default else ""
    console.print(f"  [bold]{label}[/bold]{hint_str}{default_str}: ", end="")
    value = input().strip()
    return value or default


def guided_wizard() -> dict:
    """Interactive wizard when no CLI args provided."""
    console.print("\n[bold green]🚗 Car Price Search[/bold green]")
    console.print("[dim]No arguments provided — starting guided search.[/dim]")
    console.print("[dim]Tip: use --make --model --zip for scripted/CI use.[/dim]\n")
    console.print("─" * 50)

    make = _prompt("Make", hint="toyota · honda · lexus · ford · chevrolet")
    while not make:
        console.print("  [red]Make is required.[/red]")
        make = _prompt("Make")

    model = _prompt("Model", hint="sienna · odyssey · tx · grand highlander")
    while not model:
        console.print("  [red]Model is required.[/red]")
        model = _prompt("Model")

    zip_code = _prompt("Your ZIP code", hint="used for local search radius")
    while not zip_code or not zip_code.isdigit() or len(zip_code) != 5:
        console.print("  [red]Enter a valid 5-digit US ZIP code.[/red]")
        zip_code = _prompt("Your ZIP code")

    year_range = _prompt("Year range", hint="e.g. 2022-2024 or single year like 2022", default="any")
    year_min = year_max = None
    if year_range and year_range != "any":
        parts = year_range.replace("–", "-").split("-")
        try:
            year_min = int(parts[0].strip())
            year_max = int(parts[1].strip()) if len(parts) > 1 else None
        except (ValueError, IndexError):
            try:
                year_min = int(year_range.strip())
            except ValueError:
                pass

    max_price_str = _prompt("Max price", hint="e.g. 50000", default="no limit")
    max_price = None
    if max_price_str and max_price_str != "no limit":
        try:
            max_price = int(max_price_str.replace(",", "").replace("$", ""))
        except ValueError:
            pass

    sources_str = _prompt("Sources", hint="all · or: cars cargurus autotrader carmax", default="all")
    sources = None
    if sources_str and sources_str.lower() != "all":
        sources = [s.strip().lower() for s in sources_str.split() if s.strip().lower() in SUPPORTED_SOURCES]

    console.print("─" * 50)
    return {
        "make": make, "model": model, "zip": zip_code,
        "year_min": year_min, "year_max": year_max,
        "max_price": max_price, "max_miles": 80000,
        "sources": sources, "format": "table", "save": False,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch used car prices from Cars.com, CarGurus, AutoTrader, and CarMax",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py --make toyota --model sienna --zip 10001
  python3 main.py --make honda --model odyssey --zip 10001 --year-min 2022
  python3 main.py --make lexus --model tx --zip 90210 --year-min 2024 --max-price 60000
  python3 main.py --make toyota --model "grand highlander" --zip 98101 --year-min 2024

Run without arguments for guided interactive mode:
  python3 main.py
        """,
    )
    parser.add_argument("--make", help="Car make (e.g. toyota, honda, lexus)")
    parser.add_argument("--model", help='Car model (e.g. sienna, "grand highlander")')
    parser.add_argument("--zip", help="ZIP code for search radius")
    parser.add_argument("--year-min", type=int, help="Minimum model year")
    parser.add_argument("--year-max", type=int, help="Maximum model year")
    parser.add_argument("--max-price", type=int, help="Maximum price filter")
    parser.add_argument("--max-miles", type=int, default=80000, help="Maximum mileage (default: 80000)")
    parser.add_argument("--save", action="store_true", help="Save results to output/ as JSON")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table",
                        help="Output format: table (default), json, csv")
    parser.add_argument("--sources", nargs="+", choices=SUPPORTED_SOURCES,
                        help="Sources to search (default: all). e.g. --sources cars cargurus")
    return parser.parse_args()


async def main():
    args = parse_args()

    # If required args missing → launch guided wizard
    if not args.make or not args.model or not args.zip:
        params = guided_wizard()
    else:
        params = {
            "make": args.make, "model": args.model, "zip": args.zip,
            "year_min": args.year_min, "year_max": args.year_max,
            "max_price": args.max_price, "max_miles": args.max_miles,
            "sources": args.sources, "format": args.format, "save": args.save,
        }

    console.print(f"\n[dim]{datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]")

    result = await search(
        make=params["make"],
        model=params["model"],
        zip_code=params["zip"],
        year_min=params.get("year_min"),
        year_max=params.get("year_max"),
        max_price=params.get("max_price"),
        max_miles=params.get("max_miles", 80000),
        sources=params.get("sources"),
    )

    display_results(result, fmt=params.get("format", "table"))

    if params.get("save"):
        import os
        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        make_slug = params["make"].lower()
        model_slug = params["model"].lower().replace(" ", "_")
        fname = f"output/{make_slug}_{model_slug}_{ts}.json"
        with open(fname, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"\n[dim]Saved: {fname}[/dim]")

    if args.save:
        import os
        os.makedirs("output", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"output/{args.make}_{args.model.replace(' ', '_')}_{ts}.json"
        with open(fname, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"\n[dim]Saved: {fname}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
