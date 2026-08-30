"""
HTML comparison report generator.

Reads JSON snapshots from output/ and generates a clean HTML comparison
table — open in any browser, no dependencies required.

Usage:
    python3 scripts/generate_report.py
    python3 scripts/generate_report.py --output my_report.html
    python3 scripts/generate_report.py --make toyota --model sienna
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path


STYLE = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #e6edf3; padding: 2rem; }
  h1 { font-size: 1.6rem; margin-bottom: 0.3rem; }
  .subtitle { color: #8b949e; font-size: 0.9rem; margin-bottom: 2rem; }
  .vehicle { margin-bottom: 3rem; }
  .vehicle h2 { font-size: 1.1rem; color: #58a6ff; margin-bottom: 1rem;
                border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { background: #161b22; color: #8b949e; font-weight: 600; padding: 0.6rem 1rem;
       text-align: left; border-bottom: 1px solid #30363d; }
  td { padding: 0.55rem 1rem; border-bottom: 1px solid #21262d; }
  tr:hover td { background: #161b22; }
  .price { font-weight: 700; color: #3fb950; }
  .deal-great, .deal-good { color: #3fb950; }
  .deal-fair { color: #d29922; }
  .deal-high, .deal-over { color: #f85149; }
  .stats { margin-top: 0.8rem; display: flex; gap: 2rem; color: #8b949e;
           font-size: 0.82rem; }
  .stats span b { color: #e6edf3; }
  .empty { color: #8b949e; font-style: italic; padding: 1rem 0; }
  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px;
           font-size: 0.75rem; background: #21262d; color: #8b949e; margin-left: 0.5rem; }
</style>
"""


def deal_class(deal: str) -> str:
    if not deal:
        return ""
    d = deal.lower()
    if "great" in d:
        return "deal-great"
    if "good" in d:
        return "deal-good"
    if "fair" in d:
        return "deal-fair"
    if "high" in d:
        return "deal-high"
    if "over" in d:
        return "deal-over"
    return ""


def load_snapshots(output_dir: str, make: str = None, model: str = None) -> list[dict]:
    snapshots = []
    for f in sorted(Path(output_dir).glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            if make and make.lower() not in data.get("vehicle", "").lower():
                continue
            if model and model.lower() not in data.get("vehicle", "").lower():
                continue
            data["_file"] = str(f)
            data["_date"] = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d")
            snapshots.append(data)
        except Exception:
            continue
    return snapshots


def render_vehicle(snap: dict) -> str:
    vehicle = snap.get("vehicle", "Unknown")
    date = snap.get("_date", "")
    listings = snap.get("listings", [])

    rows = ""
    for l in listings:
        price = f"${l['price']:,}" if l.get("price") else "—"
        year = str(l["year"]) if l.get("year") else "—"
        miles = f"{l['miles']:,}" if l.get("miles") else "—"
        deal = l.get("deal") or "—"
        monthly = l.get("monthly") or "—"
        source = l.get("source") or "—"
        dc = deal_class(deal)
        rows += f"""
        <tr>
          <td class="price">{price}</td>
          <td>{year}</td>
          <td>{miles}</td>
          <td class="{dc}">{deal}</td>
          <td>{monthly}</td>
          <td>{source}</td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="6" class="empty">No listings found in this snapshot.</td></tr>'

    prices = [l["price"] for l in listings if l.get("price")]
    stats = ""
    if prices:
        stats = f"""
        <div class="stats">
          <span>Range: <b>${min(prices):,} – ${max(prices):,}</b></span>
          <span>Median: <b>${sorted(prices)[len(prices)//2]:,}</b></span>
          <span>Listings: <b>{len(prices)}</b></span>
        </div>"""

    return f"""
    <div class="vehicle">
      <h2>{vehicle} <span class="badge">{date}</span></h2>
      <table>
        <thead>
          <tr>
            <th>Price</th><th>Year</th><th>Miles</th>
            <th>Deal</th><th>Monthly</th><th>Source</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      {stats}
    </div>"""


def generate(snapshots: list[dict], output_path: str) -> None:
    body = "".join(render_vehicle(s) for s in snapshots)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>carrecon — Price Comparison Report</title>
  {STYLE}
</head>
<body>
  <h1>🚗 carrecon — Price Comparison Report</h1>
  <p class="subtitle">Generated {ts} · <a href="https://github.com/TushGoel/carrecon" style="color:#58a6ff">github.com/TushGoel/carrecon</a></p>
  {body if body else '<p class="empty">No snapshots found. Run <code>python3 main.py --save</code> first.</p>'}
</body>
</html>"""
    Path(output_path).write_text(html)
    print(f"✅ Report generated: {output_path}")
    print(f"   Open in browser: open {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate HTML price comparison report")
    parser.add_argument("--output", default="output/report.html", help="Output HTML file path")
    parser.add_argument("--make", help="Filter by make")
    parser.add_argument("--model", help="Filter by model")
    parser.add_argument("--dir", default="output", help="Input directory with JSON snapshots")
    args = parser.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    snapshots = load_snapshots(args.dir, args.make, args.model)

    if not snapshots:
        print(f"No snapshots found in {args.dir}/")
        print("Run: python3 main.py --make toyota --model sienna --zip 10001 --save")
        return

    print(f"Loaded {len(snapshots)} snapshot(s)")
    generate(snapshots, args.output)


if __name__ == "__main__":
    main()
