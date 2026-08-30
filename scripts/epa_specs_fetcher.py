#!/usr/bin/env python3
"""
EPA Car Specs Fetcher
Fetches official EPA MPG data for any vehicle using the fueleconomy.gov free API.
Usage: python3 scripts/epa_specs_fetcher.py
"""

import requests
import json

EPA_BASE = "https://www.fueleconomy.gov/ws/rest"

def get_vehicle_ids(year, make, model):
    """Get all vehicle IDs for a year/make/model combo."""
    url = f"{EPA_BASE}/vehicle/menu/options?year={year}&make={make}&model={model}"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    menuItems = data.get("menuItem", [])
    if isinstance(menuItems, dict):
        menuItems = [menuItems]
    return menuItems

def get_vehicle_mpg(vehicle_id):
    """Get MPG data for a specific vehicle ID."""
    url = f"{EPA_BASE}/vehicle/{vehicle_id}"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

def get_models(year, make):
    """List all models for a make/year."""
    url = f"{EPA_BASE}/vehicle/menu/model?year={year}&make={make}"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
    if r.status_code != 200:
        return []
    data = r.json()
    items = data.get("menuItem", [])
    if isinstance(items, dict):
        items = [items]
    return [i.get("value", "") for i in items]

def fetch_car_mpg(year, make, model_keyword, awd_only=True):
    """Find all trims of a car and return MPG data, filtering for AWD/hybrid."""
    print(f"\n{'='*60}")
    print(f"Fetching: {year} {make} (searching '{model_keyword}')")
    print('='*60)

    # Get all models for this make
    models = get_models(year, make)
    matching = [m for m in models if model_keyword.lower() in m.lower()]

    if not matching:
        print(f"  No models found matching '{model_keyword}'")
        print(f"  Available models: {models[:10]}")
        return []

    results = []
    for model in matching:
        options = get_vehicle_ids(year, make, model)
        for opt in options:
            text = opt.get("text", "").lower()
            vid = opt.get("value", "")
            # Filter for AWD and hybrid variants
            is_awd = any(x in text for x in ["awd", "4wd", "4x4", "all-wheel", "all wheel"])
            is_hybrid = any(x in text for x in ["hybrid", "phev", "plug-in", "500h", "350h"])

            if awd_only and not is_awd:
                continue

            mpg_data = get_vehicle_mpg(vid)
            if not mpg_data:
                continue

            city = mpg_data.get("city08", "N/A")
            hwy = mpg_data.get("highway08", "N/A")
            comb = mpg_data.get("comb08", "N/A")
            fuel = mpg_data.get("fuelType1", "")
            tranny = mpg_data.get("trany", "")
            drive = mpg_data.get("drive", "")
            cylinders = mpg_data.get("cylinders", "")
            displ = mpg_data.get("displ", "")

            entry = {
                "model": model,
                "trim": opt.get("text", ""),
                "id": vid,
                "city": city,
                "highway": hwy,
                "combined": comb,
                "fuel": fuel,
                "drive": drive,
                "transmission": tranny,
                "hybrid": is_hybrid,
            }
            results.append(entry)

            flag = "🔋 HYBRID" if is_hybrid else ""
            print(f"  {model} | {opt.get('text','')[:50]}")
            print(f"    MPG: {city} city / {hwy} hwy / {comb} combined | {drive} {flag}")

    return results

def compare_cars(cars_config):
    """Fetch and compare multiple cars side by side."""
    all_results = {}
    for cfg in cars_config:
        key = f"{cfg['year']} {cfg['make']} {cfg['model_kw']}"
        results = fetch_car_mpg(cfg["year"], cfg["make"], cfg["model_kw"])
        all_results[key] = results

    # Print best hybrid AWD trims
    print(f"\n{'='*70}")
    print("BEST HYBRID AWD TRIMS — OFFICIAL EPA DATA")
    print('='*70)
    print(f"{'Vehicle':<35} {'City':>5} {'Hwy':>5} {'Comb':>5} {'Drive':<20}")
    print("-"*70)

    for key, results in all_results.items():
        hybrids = [r for r in results if r["hybrid"]]
        if not hybrids:
            hybrids = results  # fall back to all AWD
        for r in hybrids[:3]:
            name = f"{key[:30]}"
            print(f"{name:<35} {r['city']:>5} {r['highway']:>5} {r['combined']:>5} {r['drive'][:20]:<20}")

if __name__ == "__main__":
    cars = [
        {"year": 2025, "make": "Toyota", "model_kw": "Sienna"},
        {"year": 2025, "make": "Toyota", "model_kw": "Grand Highlander"},
        {"year": 2025, "make": "Lexus",  "model_kw": "TX"},
    ]
    compare_cars(cars)
