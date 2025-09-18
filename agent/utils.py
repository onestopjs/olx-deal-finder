"""Utilities for the agent."""

from .olx.models import OlxSearchResult


def add_and_deduplicate_search_results(
    a: list[OlxSearchResult], b: list[OlxSearchResult]
) -> list[OlxSearchResult]:
    """Add two lists of search results and deduplicate them based on URL."""
    seen_urls = set()
    result = []

    # Process first list
    for item in a:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            result.append(item)

    # Process second list
    for item in b:
        if item["url"] not in seen_urls:
            seen_urls.add(item["url"])
            result.append(item)

    return result
