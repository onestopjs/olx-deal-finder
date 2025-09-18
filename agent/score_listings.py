"""Score listings based on relevance and price."""

import logging

from langchain_core.messages import AIMessage
from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate

from .common import ScoredListing, State, base_llm, get_history_summary
from .settings import settings
from langgraph.config import get_stream_writer


class ListingScore(BaseModel):
    """Score for a listing."""

    score: int


score_prompt = PromptTemplate.from_template("""
Assign a score from 0 to 10 based on how well the ad matches the user’s prompt and desired product.

Scoring rubric:
- 0 = Completely irrelevant (wrong product, category, or only accessories without the main product).
- 1–3 = Slightly related (mentions brand or vague category but not the desired product; or product is broken/non-functional).
- 4–6 = Somewhat relevant (mentions the product but missing key details, unclear condition, or mismatched context).
- 7–9 = Mostly relevant (the product matches the request, only minor wording/attribute mismatch).
- 10 = Perfect match (title and description clearly align with the prompt and desired product, with no contradictions).

Guidelines:
- Consider BOTH title and description together.
- Use semantic meaning, not just keyword overlap.
- Ignore SEO keyword stuffing or unrelated mentions if the actual product is clear.
- Do not give a high score if the ad is only for parts, accessories, or non-functional devices unless the user explicitly asked for them.

====User prompt:====
{prompt}

====Desired product(s):====
{products}

====Ad title:====
{title}

====Ad description:====
{description}
""")


score_llm = base_llm.with_structured_output(
    ListingScore,
    method="json_schema" if not settings.tool_calling_enabled else "function_calling",
)


def get_normalized_scores(
    relevancy_score,
    listing_price,
    median_price,
    max_price_ratio=5,
    clamp=True,
):
    """Compute combined score from normalized relevance and price using a weighted geometric mean.

    - Relevance is normalized to [0,1] by dividing the 0–10 LLM score by 10.
    - Price is normalized to [0,1] by computing (median / price) scaled by a
      max_price_ratio and clamped to [0,1]. This penalizes expensive items and
      gives diminishing returns to very cheap items.
    - The final score is the weighted geometric mean of the two normalized scores,
      ensuring that an irrelevant item cannot achieve a high score purely by being
      cheap, and expensive items are punished even if relevant.

    Returns a tuple: (price_score_0_10, relevancy_score_0_10, combined_0_10)
    """
    relevance_norm = max(0.0, min(1.0, (relevancy_score or 0) / 10.0))
    gamma = (
        float(settings.relevancy_gamma) if hasattr(settings, "relevancy_gamma") else 1.0
    )
    if gamma and gamma != 1.0:
        relevance_norm = relevance_norm**gamma

    if not listing_price or listing_price <= 0 or not median_price or median_price <= 0:
        price_norm = 1.0
    else:
        ratio = median_price / float(listing_price)
        price_norm = ratio / float(max_price_ratio)
        if clamp:
            price_norm = max(0.0, min(1.0, price_norm))
        else:
            price_norm = max(0.0, price_norm)

    w_rel = float(settings.relevancy_score_weight or 1)
    w_price = float(settings.price_score_weight or 1)
    w_sum = w_rel + w_price
    a = w_rel / w_sum
    b = w_price / w_sum

    final_norm = (relevance_norm**a) * (price_norm**b)

    price_score_norm_0_10 = round(price_norm * 10.0, 4)
    combined_score_0_10 = round(final_norm * 10.0, 4)

    return price_score_norm_0_10, relevancy_score, combined_score_0_10


logger = logging.getLogger(__name__)


def score_listings(state: State) -> State:
    """Score listings."""

    writer = get_stream_writer()

    scored_listings = []
    filtered_listings = state["filtered_listings"]
    writer(
        {"stage": "score_listings", "listings_count": len(state["filtered_listings"])}
    )
    for listing_idx, listing in enumerate(filtered_listings):
        logger.info(
            "scoring listing",
            extra={
                "idx": listing_idx + 1,
                "total": len(filtered_listings),
                "title": listing.get("title"),
            },
        )
        if not listing:
            scored_listings = {
                "filtered_listings": state["filtered_listings"],
            }

        median_price = state["median_price"]

        # find the last user prompt from messages
        user_prompt = get_history_summary(state["messages"])

        logger.debug(
            "user prompt for scoring", extra={"prompt_preview": user_prompt[:120]}
        )

        prompt = score_prompt.invoke(
            {
                "prompt": user_prompt,
                "products": state["products"],
                "title": listing["title"],
                "description": listing["description"],
            }
        )

        relevancy_score_raw = score_llm.invoke(prompt)

        relevancy_score = relevancy_score_raw.score
        price_score_norm, relevancy_score, combined_score = get_normalized_scores(
            relevancy_score, listing["price_value"], median_price
        )

        logger.info(
            "listing scored",
            extra={
                "idx": listing_idx + 1,
                "total": len(filtered_listings),
                "title": listing.get("title"),
                "relevancy_score": relevancy_score,
                "price_score_norm": price_score_norm,
                "combined_score": combined_score,
            },
        )

        scored_listing = ScoredListing(
            listing=listing,
            relevancy_score=relevancy_score,
            price_score=price_score_norm,
            combined_score=combined_score,
        )

        scored_listings.append(scored_listing)

        writer(
            {
                "stage": "score_listings_progress",
                "scored_listings_count": len(scored_listings),
                "total_listings_count": len(filtered_listings),
            }
        )

    response = AIMessage(content=f"Scored {len(scored_listings)} listings")

    return {
        "filtered_listings": state["filtered_listings"][1:],
        "scored_listings": scored_listings,
        "messages": [response],
    }
