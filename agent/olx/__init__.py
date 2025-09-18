"""OLX Scraper Package.

A Python package for scraping and parsing OLX.bg advertisements and search results.
"""

from .models import OlxSearchResult
from .search import search_olx_ads

__version__ = "1.0.0"
__all__ = [
    "search_olx_ads",
    "OlxSearchResult",
]
