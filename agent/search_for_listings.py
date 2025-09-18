"""Search for listings."""

import logging

from .olx.search import search_olx_ads
from langgraph.config import get_stream_writer

from .common import State
from .settings import settings


logger = logging.getLogger(__name__)


def search_for_listings(state: State) -> State:
    """Search for listings."""

    writer = get_stream_writer()

    search_query = state["search_queries"][0]
    writer({"stage": "search_for_listings", "search_query": search_query})

    if not search_query:
        logger.warning("no search query present")
        return {
            "potential_listings": [],
        }

    new_potential_listings = []
    for page in range(1, settings.max_pages_to_search + 1):
        logger.info("searching", extra={"query": search_query, "page": page})
        potential_listings, has_more_pages = search_olx_ads(search_query, page)
        new_potential_listings.extend(potential_listings)
        if not has_more_pages:
            break

    logger.info(
        "found potential listings", extra={"count": len(new_potential_listings)}
    )

    return {
        "potential_listings": new_potential_listings,
        "search_queries": state["search_queries"][1:],
    }


def should_continue_searching(state: State) -> str:
    """Determine if the agent should continue searching for listings."""
    return "search_for_listings" if state["search_queries"] else "continue"
