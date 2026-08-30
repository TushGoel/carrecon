"""Tests for the price extraction / parsing logic."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import extract_listings


def test_extracts_price_from_line():
    lines = ["Used 2023 Toyota Sienna $43,758 Good Deal Est. $808/mo 28,400 miles"]
    results = extract_listings(lines, "Cars.com")
    assert len(results) == 1
    assert results[0]["price"] == 43758


def test_extracts_year():
    lines = ["2022 Toyota Sienna XSE $39,500"]
    results = extract_listings(lines, "CarGurus")
    assert results[0]["year"] == 2022


def test_extracts_mileage():
    lines = ["$41,000 32,500 miles Good Deal"]
    results = extract_listings(lines, "Cars.com")
    assert results[0]["miles"] == 32500


def test_extracts_deal_rating():
    lines = ["$40,000 Great Deal Est. $740/mo 2022"]
    results = extract_listings(lines, "Cars.com")
    assert results[0]["deal"] == "Great Deal"


def test_extracts_monthly_payment():
    lines = ["$43,758 Good Deal Est. $808/mo 2023"]
    results = extract_listings(lines, "Cars.com")
    assert results[0]["monthly"] == "$808/mo"


def test_filters_implausible_prices():
    lines = ["$50 item for sale", "$5,000,000 mansion"]
    results = extract_listings(lines, "Cars.com")
    assert len(results) == 0


def test_deduplicates_same_price():
    lines = [
        "$43,758 Good Deal 2023 28,000 miles",
        "$43,758 Good Deal 2023",  # same price
    ]
    results = extract_listings(lines, "Cars.com")
    assert len(results) == 1


def test_sorts_by_price():
    lines = [
        "$50,000 2024 5,000 miles",
        "$35,000 2022 45,000 miles Good Deal",
        "$42,000 2023 28,000 miles Fair Deal",
    ]
    results = extract_listings(lines, "Cars.com")
    prices = [r["price"] for r in results]
    assert prices == sorted(prices)


def test_returns_empty_for_no_prices():
    lines = ["Toyota Sienna AWD Hybrid", "Great family car", "Excellent condition"]
    results = extract_listings(lines, "Cars.com")
    assert results == []


def test_source_attached():
    lines = ["$40,000 Good Deal 2023"]
    results = extract_listings(lines, "AutoTrader")
    assert results[0]["source"] == "AutoTrader"
