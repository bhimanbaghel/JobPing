from .base import BaseScraper, ScrapedJob
from .airbnb import AirbnbScraper
from .coinbase import CoinbaseScraper
from .palantir import PalantirScraper
from .plaid import PlaidScraper
from .spotify import SpotifyScraper
from .stripe import StripeScraper

SCRAPER_REGISTRY = [
    AirbnbScraper(),
    StripeScraper(),
    CoinbaseScraper(),
    SpotifyScraper(),
    PalantirScraper(),
    PlaidScraper(),
]

__all__ = [
    "BaseScraper",
    "ScrapedJob",
    "SCRAPER_REGISTRY",
    "AirbnbScraper",
    "CoinbaseScraper",
    "PalantirScraper",
    "PlaidScraper",
    "SpotifyScraper",
    "StripeScraper",
]
