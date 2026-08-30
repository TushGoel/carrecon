# carrecon

![CI](https://github.com/TushGoel/carrecon/actions/workflows/ci.yml/badge.svg)
![Weekly Price Tracker](https://github.com/TushGoel/carrecon/actions/workflows/weekly_price_track.yml/badge.svg)

**Live car prices from sites that block everyone else.**

An open-source tool that fetches **used car prices from Cars.com and CarGurus** and **official specs from the EPA** — bypassing bot protection using Playwright with stealth mode.

Works for **any make, model, year range, and ZIP code.**

---

## Why I Built This

I was researching a family car purchase and spent hours manually clicking through bot checks on Cars.com, CarGurus, and Edmunds — copying prices into a spreadsheet, refreshing pages, losing data. I asked AI assistants for help. Every one of them hit the same wall: **bot detection blocks AI access to every major car site.**

So I built the bypass. This tool runs a real Chromium browser with stealth mode — indistinguishable from a human visitor — aggregates live prices across all four major used car sites and six manufacturer websites, extracts structured data, and lets you search any car with a single command.

**Built and tested using Claude Code as the development environment.** What used to take hours of manual browsing now takes one command.

40M+ used cars are sold annually in the US. Every buyer wastes hours on this exact problem.

---

## Weekly Price History

A GitHub Actions cron runs every Monday and commits fresh price snapshots to `output/`. Browse the price history to track depreciation over time.

---

## The Problem

Every major car listing site blocks automated access:
- Cars.com, CarGurus, AutoTrader → Cloudflare / bot detection
- Toyota.com, Lexus.com → 403 on simple HTTP requests
- KBB, Edmunds → rate limiting + auth walls

This tool runs a **real browser with stealth mode** that sites cannot distinguish from a human visitor — then extracts and structures the pricing data.

---

## What It Does

| Feature | How |
|---------|-----|
| **Used car prices** | Playwright stealth → Cars.com, CarGurus, AutoTrader, CarMax |
| **New car MSRP** | Playwright stealth → Toyota, Lexus, Honda, Hyundai, Ford, Chevrolet |
| **Official MPG data** | EPA fueleconomy.gov free API (no auth required) |
| **Structured output** | Price, year, mileage, deal rating, monthly payment |
| **Multiple output formats** | Table (default), JSON, CSV |
| **Source selection** | `--sources cars cargurus autotrader carmax` |
| **Price trend analysis** | `scripts/analyze_history.py` — track depreciation over time |
| **Weekly price tracking** | GitHub Actions cron — auto-commits snapshots every Monday |

> All sites listed block standard HTTP requests. This tool bypasses bot detection using Playwright stealth mode — running a real Chromium browser indistinguishable from a human visitor.

---

## System Design

```mermaid
graph TD
    A[CLI\n--make --model --zip\n--year-min --format --sources] --> B[URL Builder\nper source]

    subgraph Sources_Bypassed_With_Playwright_Stealth
        B --> C[Cars.com]
        B --> D[CarGurus]
        B --> E[AutoTrader]
        B --> F[CarMax]
    end

    C & D & E & F --> G[Raw Text\ninner_text extraction]
    G --> H[Price Parser\nregex extraction]
    H --> I[Structured Listings\nprice · year · miles\ndeal rating · monthly]
    I --> J{Output Format}
    J -->|table| K[Rich Table\nmin · max · median]
    J -->|json| L[JSON output]
    J -->|csv| M[CSV output]
    I --> N[output/ JSON\nweekly GitHub Actions cron]
    N --> O[analyze_history.py\nprice trend analysis]
```

## Setup

```bash
git clone https://github.com/TushGoel/car-research.git
cd car-research

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

---

## Usage

### Search used car prices

```bash
# Basic search
python3 main.py --make toyota --model sienna --zip 75080

# With year range and price cap
python3 main.py --make honda --model odyssey --zip 10001 --year-min 2022 --max-price 45000

# Save results to JSON
python3 main.py --make lexus --model tx --zip 98101 --year-min 2024 --save

# Multi-word model name
python3 main.py --make toyota --model "grand highlander" --zip 90210 --year-min 2024
```

### Options

```
--make         Car make (toyota, honda, lexus, ford, ...)
--model        Car model (sienna, odyssey, tx, ...)
--zip          ZIP code for search radius
--year-min     Minimum model year
--year-max     Maximum model year
--max-price    Maximum price filter
--max-miles    Maximum mileage (default: 80,000)
--save         Save results to output/ as JSON
```

### Get official new car MSRP from manufacturer websites

Toyota, Lexus, Honda, Hyundai, Ford, Chevrolet all block standard HTTP requests.
This tool bypasses their bot detection to fetch official pricing and trim data:

```bash
# List available models for a manufacturer
python3 scripts/new_car_prices.py --list-models toyota

# Fetch MSRP for a specific model
python3 scripts/new_car_prices.py --make toyota --model sienna
python3 scripts/new_car_prices.py --make lexus --model tx
python3 scripts/new_car_prices.py --make honda --model odyssey --save
```

### Get official EPA MPG data

```bash
python3 scripts/epa_specs_fetcher.py
```

---

## Example Output

```
══════════════════════════════════════════════════════════
🔍 TOYOTA SIENNA (2022–2024) near 75080
══════════════════════════════════════════════════════════

┌─────────────┬──────┬────────┬────────────┬─────────┬──────────┐
│       Price │ Year │  Miles │ Deal       │ Monthly │ Source   │
├─────────────┼──────┼────────┼────────────┼─────────┼──────────┤
│     $39,500 │ 2022 │ 41,200 │ Good Deal  │ $729/mo │ Cars.com │
│     $41,888 │ 2023 │ 28,500 │ Fair Deal  │ $772/mo │ CarGurus │
│     $43,758 │ 2024 │ 12,100 │ Good Deal  │ $808/mo │ Cars.com │
└─────────────┴──────┴────────┴────────────┴─────────┴──────────┘

  Range:    $39,500 – $47,200
  Median:   $43,758
  Listings: 8
```

---

## Project Structure

```
car-research/
├── main.py                    # CLI entry point — search any car
├── requirements.txt
├── scrapers/
│   ├── base.py                # Stealth Playwright base class
│   ├── cargurus.py            # CarGurus scraper
│   └── __init__.py
├── scripts/
│   ├── epa_specs_fetcher.py   # Official MPG via EPA API
│   └── toyota_lexus_scraper.py
├── docs/
│   └── Test_Drive_Guide.html  # Interactive test drive checklist
└── data/
    └── toyota_lexus_official_specs.json
```

---

## Design Decisions & Trade-offs

**Why Playwright over requests/BeautifulSoup:**
Every major car site uses Cloudflare or custom bot detection. Simple HTTP requests return 403/blocked responses. Playwright runs a real Chromium browser — identical to a human visitor. Stealth mode patches the `navigator.webdriver` flag and other bot-detection signals.

**Why regex over DOM selector parsing:**
Car listing sites change their HTML structure frequently — a CSS selector that works today breaks after their next deploy. Regex on `innerText` is more resilient: it targets the content (prices, years, mileage) regardless of the DOM structure around it.

**Why multi-source by default:**
Each site has different inventory, different deal ratings, and different data freshness. Aggregating across Cars.com, CarGurus, AutoTrader, and CarMax gives a more accurate market picture than any single source. Use `--sources` to restrict when you only want one.

**Why structured output instead of raw text:**
Raw text from `inner_text()` is noisy — it includes navigation, ads, footer text. The price parser extracts only the signal (price, year, miles, deal rating) using regex patterns that are tuned for car listing formats. This makes the output programmatically useful, not just readable.

**Why GitHub Actions cron for price tracking:**
Car prices fluctuate weekly based on supply, season, and inventory. A manual snapshot is a point-in-time view. The weekly cron turns this into a time-series dataset — you can track depreciation, spot seasonal patterns, and identify when prices are moving.

## Roadmap

- [ ] Add CarMax scraper
- [ ] Add AutoTrader scraper
- [ ] Weekly price tracking via GitHub Actions cron
- [ ] HTML comparison report generator
- [ ] KBB fair market value integration
- [ ] Add Honda, Hyundai, Kia, Ford official specs

---

## Disclaimer

For personal research only. Respect each site's terms of service.

## License

MIT
