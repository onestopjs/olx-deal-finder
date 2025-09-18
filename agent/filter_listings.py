"""Filter listings based on user request."""

import logging

from pydantic import BaseModel

from .common import State, base_llm, get_history_summary
from .settings import settings
from langgraph.config import get_stream_writer
from langchain_core.prompts import PromptTemplate


class FilterListings(BaseModel):
    """Filter listings based on user request."""

    ids_to_keep: list[int]


filter_listings_prompt = PromptTemplate.from_template("""Select only the listing IDs relevant to the user's desired products.

Rules:
- If include_configurations = True: keep listings that contain the desired product, even if part of a larger configuration/bundle.
- If include_configurations = False: keep only listings that sell exactly the desired product. Exclude configurations/bundles.
- Unless the product itself is an accessory, exclude listings that are accessories for the desired product.
    
Include configurations: {include_configurations}

User prompt:
{prompt}

User desired products:
{user_desired_products}

Listings:
{listings_string}
""")

filter_listings_llm = base_llm.with_structured_output(
    FilterListings,
    method="json_schema" if not settings.tool_calling_enabled else "function_calling",
)


logger = logging.getLogger(__name__)


def filter_listings(state: State) -> State:
    """Filter listings based on user request."""
    listings = state["potential_listings"]
    user_desired_products = state["products"]
    include_configurations = state["include_configurations"]

    writer = get_stream_writer()
    writer({"stage": "filter_listings", "listings_count": len(listings)})

    filtered_listings = []

    for i in range(0, len(listings), settings.listings_batch_size):
        batch = listings[i : i + settings.listings_batch_size]

        listings_string = ""

        for listing_idx, listing in enumerate(batch):
            listings_string += f"[{listing_idx}] {listing['title']}\n"

        # find the last user prompt from messages
        user_prompt = get_history_summary(state["messages"])

        prompt = filter_listings_prompt.invoke(
            {
                "include_configurations": include_configurations,
                "prompt": user_prompt,
                "user_desired_products": user_desired_products,
                "listings_string": listings_string,
            }
        )

        ids_to_keep = filter_listings_llm.invoke(prompt).ids_to_keep

        logger.info("keeping listings", extra={"count": len(ids_to_keep)})
        listings_to_keep = [
            listing
            for listing_idx, listing in enumerate(batch)
            if listing_idx in ids_to_keep
        ]

        filtered_listings.extend(listings_to_keep)

    # Filter out listings with no price and calculate average if any remain
    listings_with_price = [
        listing for listing in filtered_listings if listing["price_value"] is not None
    ]
    average_price = (
        sum(listing["price_value"] for listing in listings_with_price)
        / len(listings_with_price)
        if listings_with_price
        else 0
    )

    median_price = sorted(filtered_listings, key=lambda x: x["price_value"])[
        len(filtered_listings) // 2
    ]["price_value"]

    return {
        "filtered_listings": filtered_listings,
        "average_price": average_price,
        "median_price": median_price,
    }
