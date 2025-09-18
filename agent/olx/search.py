"""Functions for searching OLX and parsing search results."""

import logging

from .http_client import make_graphql_request
from .models import OlxSearchResult


logger = logging.getLogger(__name__)


def search_olx_ads(
    query: str, page: int = 1, limit: int = 40
) -> tuple[list[OlxSearchResult], bool]:
    """Search OLX for listings matching the query using GraphQL API.

    Args:
        query (str): The search query (e.g., "rolex watch").
        page (int): The page number to retrieve (default: 1).
        limit (int): Number of results per page (default: 40).

    Returns:
        tuple[list[OlxSearchResult], bool]: Tuple containing:
            - List of OlxSearchResult objects
            - Boolean indicating if there are more pages available
    """
    graphql_url = "https://www.olx.bg/apigateway/graphql"

    graphql_query = """
    query ListingSearchQuery($searchParameters: [SearchParameter!]!) {
        clientCompatibleListings(searchParameters: $searchParameters) {
            __typename
            ... on ListingSuccess {
                data {
                    id
                    title
                    description
                    url
                    category {
                        id
                        type
                    }
                    params {
                        key
                        value {
                            ... on PriceParam {
                                value
                                currency
                            }
                            ... on GenericParam {
                                key
                                label
                            }
                        }
                    }
                }
            }
        }
    }
    """

    offset = (page - 1) * limit

    variables = {
        "searchParameters": [
            {"key": "offset", "value": str(offset)},
            {"key": "limit", "value": str(limit)},
            {"key": "query", "value": query},
        ]
    }

    try:
        response = make_graphql_request(graphql_url, graphql_query, variables)
    except Exception as e:
        logger.exception("GraphQL request failed", exc_info=e)
        return [], False

    listings, has_more_pages = parse_graphql_response(response, page, limit)
    return listings, has_more_pages


def parse_graphql_response(
    response: dict, current_page: int = 1, limit: int = 40
) -> tuple[list[OlxSearchResult], bool]:
    """Parse GraphQL response to extract listing information and check for pagination.

    Args:
        response (dict): The GraphQL response dictionary.
        current_page (int): The current page number being parsed.
        limit (int): The number of results per page.

    Returns:
        tuple[list[OlxSearchResult], bool]: Tuple containing:
            - List of OlxSearchResult objects
            - Boolean indicating if there are more pages available
    """
    listings = []

    try:
        client_compatible_listings = response.get("data", {}).get(
            "clientCompatibleListings", {}
        )

        if client_compatible_listings.get("__typename") != "ListingSuccess":
            return listings, False

        listings_data = client_compatible_listings.get("data", [])

        for listing_data in listings_data:
            listing = parse_single_listing(listing_data)
            if listing:
                listings.append(listing)

        has_more_pages = len(listings_data) == limit

    except (KeyError, TypeError, AttributeError):
        logger.error(
            "Error parsing graphql response",
            extra={"response_snippet": str(response)[:200]},
        )
        return listings, False

    return listings, has_more_pages


def parse_single_listing(listing_data: dict) -> OlxSearchResult | None:
    """Parse a single listing from GraphQL response.

    Args:
        listing_data (dict): The listing data from GraphQL response.

    Returns:
        OlxSearchResult | None: The parsed listing or None if parsing fails.
    """
    try:
        listing_id = listing_data.get("id")
        title = listing_data.get("title", "")
        description = listing_data.get("description")
        url = listing_data.get("url", "")
        category = listing_data.get("category", {})
        params = listing_data.get("params", [])

        listing = {
            "title": title,
            "url": url,
            "description": description,
            "price_value": None,
            "price_currency": None,
            "location": None,
            "condition": None,
            "category_id": category.get("id"),
            "category_type": category.get("type"),
            "listing_id": listing_id,
        }

        for param in params:
            key = param.get("key", "")
            value = param.get("value", {})

            if key == "price":
                price_value = value.get("value")
                price_currency = value.get("currency")
                if price_value is not None:
                    listing["price_value"] = float(price_value)
                    listing["price_currency"] = price_currency

            elif key == "state":
                condition_label = value.get("label", "")
                if condition_label:
                    listing["condition"] = condition_label

            elif key == "location":
                location_label = value.get("label", "")
                if location_label:
                    listing["location"] = location_label

        if listing.get("title") and listing.get("url"):
            return OlxSearchResult(**listing)

    except (KeyError, TypeError, ValueError):
        logger.error(
            "Error parsing listing", extra={"listing_snippet": str(listing_data)[:200]}
        )
        return None

    return None
