"""Tests for URL builder functions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import cars_com_url, cargurus_url
from scrapers.cargurus import CarGurusScraper
from scrapers.autotrader import AutoTraderScraper
from scrapers.carmax import CarMaxScraper


def test_cars_com_basic():
    url = cars_com_url("toyota", "sienna", "10001")
    assert "toyota" in url
    assert "sienna" in url
    assert "10001" in url
    assert "cars.com" in url


def test_cars_com_with_filters():
    url = cars_com_url("honda", "odyssey", "10001",
                       year_min=2022, year_max=2024, max_price=45000, max_miles=60000)
    assert "year_min=2022" in url
    assert "year_max=2024" in url
    assert "list_price_max=45000" in url
    assert "mileage_max=60000" in url


def test_cargurus_basic():
    url = cargurus_url("lexus", "tx", "90210")
    assert "cargurus.com" in url
    assert "90210" in url


def test_cargurus_with_filters():
    url = cargurus_url("toyota", "sienna", "10001", year_min=2022, max_price=50000)
    assert "minYear=2022" in url
    assert "maxPrice=50000" in url


def test_cargurus_scraper_url_appends_params():
    scraper = CarGurusScraper()
    url = scraper.build_url("toyota", "sienna", "10001", year_min=2022, awd=True)
    assert "minYear=2022" in url
    assert "driveType=AWD" in url
    assert "10001" in url


def test_autotrader_url():
    scraper = AutoTraderScraper()
    url = scraper.build_url("toyota", "camry", "10001", year_min=2021, max_price=35000)
    assert "autotrader.com" in url
    assert "TOYOTA" in url
    assert "CAMRY" in url
    assert "startYear=2021" in url
    assert "maxPrice=35000" in url


def test_carmax_url():
    scraper = CarMaxScraper()
    url = scraper.build_url("honda", "cr-v", "98101")
    assert "carmax.com" in url
    assert "honda" in url
    assert "98101" in url


def test_multi_word_model():
    url = cars_com_url("toyota", "grand highlander", "10001")
    assert "grand_highlander" in url.lower() or "grand" in url.lower()
