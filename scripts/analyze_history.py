"""
Price history analyzer — reads weekly snapshots from output/ and shows trends.

Usage:
    python3 scripts/analyze_history.py
    python3 scripts/analyze_history.py --make toyota --model sienna
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def load_snapshots(output_dir: str = "output") -> list[dict]:
    """Load all JSON snapshots from the output directory."""
    snapshots = []
    for f in sorted(Path(output_dir).glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
                # Attach filename timestamp
                ts_str = f.stem.split("_")[-2] + "_" + f.stem.split("_")[-1]
                try:
                    ts = datetime.strptime(ts_str, "%Y%m%d_%H%M")
                except ValueError:
                    ts = datetime.fromtimestamp(os.path.getmtime(f))
                data["_file"] = str(f)
                data["_ts"] = ts.isoformat()
                snapshots.append(data)
        except Exception:
            pass
    return snapshots


def analyze(snapshots: list[dict], make: str = None, model: str = None) -> None:
    """Print price trend summary."""
    if not snapshots:
        print("No snapshots found in output/. Run `python3 main.py --save` first.")
        return

    # Filter by vehicle if specified
    filtered = snapshots
    if make or model:
        filtered = [
            s for s in snapshots
            if (not make or make.lower() in s.get("vehicle", "").lower())
            and (not model or model.lower() in s.get("vehicle", "").lower())
        ]

    if not filtered:
        print(f"No snapshots found for {make} {model}")
        return

    # Group by vehicle
    vehicles: dict[str, list] = {}
    for snap in filtered:
        v = snap.get("vehicle", "Unknown")
        if v not in vehicles:
            vehicles[v] = []
        listings = snap.get("listings", [])
        if listings:
            prices = [l["price"] for l in listings if l.get("price")]
            if prices:
                vehicles[v].append({
                    "date": snap["_ts"][:10],
                    "min": min(prices),
                    "median": sorted(prices)[len(prices) // 2],
                    "max": max(prices),
                    "count": len(prices),
                })

    # Print trends
    for vehicle, history in vehicles.items():
        print(f"\n{'═'*60}")
        print(f"  {vehicle}")
        print(f"{'═'*60}")
        print(f"  {'Date':<12} {'Min':>10} {'Median':>10} {'Max':>10} {'Listings':>10}")
        print(f"  {'-'*52}")
        for entry in history:
            print(
                f"  {entry['date']:<12} "
                f"${entry['min']:>9,} "
                f"${entry['median']:>9,} "
                f"${entry['max']:>9,} "
                f"{entry['count']:>10}"
            )

        if len(history) > 1:
            first = history[0]["median"]
            last = history[-1]["median"]
            delta = last - first
            pct = (delta / first) * 100 if first else 0
            direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            print(f"\n  Trend: median {direction} ${abs(delta):,} ({pct:+.1f}%) "
                  f"from {history[0]['date']} to {history[-1]['date']}")


def main():
    parser = argparse.ArgumentParser(description="Analyze price history from weekly snapshots")
    parser.add_argument("--make", help="Filter by make")
    parser.add_argument("--model", help="Filter by model")
    parser.add_argument("--dir", default="output", help="Output directory (default: output)")
    args = parser.parse_args()

    snapshots = load_snapshots(args.dir)
    print(f"Loaded {len(snapshots)} snapshot(s) from {args.dir}/")
    analyze(snapshots, args.make, args.model)


if __name__ == "__main__":
    main()
