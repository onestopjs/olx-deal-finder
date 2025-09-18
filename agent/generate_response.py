from agent.olx.models import OlxSearchResult
from agent.settings import settings
import logging
from .common import State, base_llm, get_history_summary
from langgraph.config import get_stream_writer
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AIMessage

generate_response_prompt = PromptTemplate.from_template("""
You are an assistant that helps summarize **used marketplace listings** (from OLX.bg). 
You are NOT a product reviewer and you should never describe specifications, features, or advertisements. 
Your only task is to summarize the **market situation** for the requested product(s).

Always respond in **English only**. 
If you cannot create a detailed summary, fall back to:
"We found {listings_count} listings, with a median price of {median_price}. 
Out of {potential_listings_count} potential listings, {filtered_listings_count} matched your filters."

The user asked for:
{products}

We found {listings_count} relevant listings, with a median price of {median_price}.

Write a short, natural, and conversational response that:
- Does not list specific listings.
- Does not review the product or list technical specs.
- Comments on whether the median price seems fair, high, or low.
- Mentions the total number of potential listings ({potential_listings_count}) 
  and the remaining listings after filtering ({filtered_listings_count}).

User’s original request (may be in Bulgarian, but reply in English):
{prompt}

(Reference only, do NOT show to the user: Top 5 listings: {top_5_listings})
""")


logger = logging.getLogger(__name__)


def get_listing_title(listing: OlxSearchResult) -> str:
    """Get a string representation of a listing."""

    base_title = f"{listing['listing']['title']} ({listing['listing']['price_value']} {listing['listing']['price_currency']})"

    if settings.debug_scoring:
        return f"{base_title} (score: {listing['combined_score']}, relevancy: {listing['relevancy_score']}, price: {listing['price_score']})"

    return base_title


def get_listing_string(listing: OlxSearchResult) -> str:
    """Get a string representation of a listing."""
    listing_title = get_listing_title(listing)

    if settings.enable_markdown:
        return f"- [{listing_title}]({listing['listing']['url']})"
    else:
        return f"- {listing_title} - ({listing['listing']['url']})"


def generate_response(state: State) -> State:
    """Generate a response to the user's request."""

    writer = get_stream_writer()
    writer({"stage": "generate_response"})

    # sort by combined score
    listings = sorted(
        state["scored_listings"], key=lambda x: x["combined_score"], reverse=True
    )
    listings = listings[: state["max_products_count"]]
    logger.info("selected top listings", extra={"count": len(listings)})

    user_prompt = get_history_summary(state["messages"])

    prompt = generate_response_prompt.invoke(
        {
            "products": state["products"],
            "top_5_listings": listings[:5],
            "prompt": user_prompt,
            "listings_count": len(listings),
            "potential_listings_count": len(state["potential_listings"]),
            "filtered_listings_count": len(state["filtered_listings"]),
            "median_price": state["median_price"],
        }
    )
    llm_response = base_llm.invoke(prompt)
    logger.debug("llm responded for generate_response")

    listings_string = ""
    for listing in listings:
        listings_string += f"{get_listing_string(listing)}\n"

    response = f"""{llm_response.content}

{listings_string}
    """

    # append AI message to messages
    return {"messages": [AIMessage(content=response)]}
