"""Mock-based scraper tests — run without a real browser or network.

These tests mock the Playwright page object so CI passes without Playwright
installed. Only logic is tested: schema.org extraction, text parsing, dedup.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main import extract_listings, _try_schema_org


# ── Schema.org extraction ─────────────────────────────────────────────────────

SCHEMA_LISTING = json.dumps({
    "@context": "https://schema.org",
    "@type": "Car",
    "name": "2023 Toyota Sienna",
    "vehicleModelDate": "2023",
    "offers": {"@type": "Offer", "price": "43758", "priceCurrency": "USD"},
    "mileageFromOdometer": {"value": 28400},
})

SCHEMA_NO_CARS = json.dumps({"@type": "WebPage", "name": "Cars for Sale"})


@pytest.mark.asyncio
async def test_schema_org_extracts_listing():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=[SCHEMA_LISTING])
    result = await _try_schema_org(page)
    assert len(result) == 1
    assert result[0]["price"] == 43758
    assert result[0]["year"] == "2023"


@pytest.mark.asyncio
async def test_schema_org_returns_empty_for_no_cars():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=[SCHEMA_NO_CARS])
    result = await _try_schema_org(page)
    assert result == []


@pytest.mark.asyncio
async def test_schema_org_returns_empty_on_error():
    page = AsyncMock()
    page.evaluate = AsyncMock(side_effect=Exception("Browser error"))
    result = await _try_schema_org(page)
    assert result == []


@pytest.mark.asyncio
async def test_schema_org_handles_malformed_json():
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=["{not valid json}"])
    result = await _try_schema_org(page)
    assert result == []


# ── Full scrape mock (tests pipeline without real browser) ────────────────────

def _make_mock_browser(page_mock):
    """Build a properly-wired async browser mock."""
    mock_ctx = AsyncMock()
    mock_ctx.new_page = AsyncMock(return_value=page_mock)
    mock_ctx.close = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)
    mock_browser.close = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
    return mock_playwright


@pytest.mark.asyncio
async def test_scrape_one_source_uses_schema_when_available():
    """When schema.org data is available, skip regex parsing entirely."""
    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=[SCHEMA_LISTING])
    mock_page.inner_text = AsyncMock(return_value="")

    mock_pw = _make_mock_browser(mock_page)
    mock_stealth = MagicMock()
    mock_stealth.return_value.apply_stealth_async = AsyncMock()

    with patch("main.Stealth", mock_stealth), patch("asyncio.sleep", new_callable=AsyncMock):
        from main import scrape_one_source
        result = await scrape_one_source(mock_pw, "https://cars.com/test", "Cars.com")

    assert len(result) == 1
    assert result[0]["price"] == 43758
    mock_page.inner_text.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_one_source_falls_back_to_regex():
    """When schema.org returns nothing, fall back to regex on inner_text."""
    raw_text = "Used 2022 Toyota Sienna $41,000 Good Deal 35,000 miles Est. $760/mo"

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=[])
    mock_page.inner_text = AsyncMock(return_value=raw_text)

    mock_pw = _make_mock_browser(mock_page)
    mock_stealth = MagicMock()
    mock_stealth.return_value.apply_stealth_async = AsyncMock()

    with patch("main.Stealth", mock_stealth), \
         patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("main._try_llm_fallback", new_callable=AsyncMock, return_value=[]):
        from main import scrape_one_source
        result = await scrape_one_source(mock_pw, "https://cars.com/test", "Cars.com")

    assert isinstance(result, list)
    assert any("$41,000" in str(r) for r in result)
