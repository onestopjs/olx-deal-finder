"""Common state for the agent."""

import operator
from typing_extensions import Annotated, TypedDict
from langchain_core.messages import BaseMessage

from langchain_ollama.chat_models import ChatOllama
from langchain_openai.chat_models import ChatOpenAI
from langchain_anthropic.chat_models import ChatAnthropic

from .olx.models import OlxSearchResult

from .settings import settings
from .utils import add_and_deduplicate_search_results


def get_base_llm():
    if settings.llm_provider == "ollama":
        return ChatOllama(base_url=settings.ollama_url, model=settings.ollama_model)
    elif settings.llm_provider == "openai":
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_url,
        )
    elif settings.llm_provider == "anthropic":
        return ChatAnthropic(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
    else:
        raise ValueError(f"Invalid LLM provider: {settings.llm_provider}")


def get_history_summary(messages: list[BaseMessage]) -> str:
    """Get a summary of the chat history in plain English only."""
    return "\n".join(
        [
            f"(User request, possibly non-English, for context only): {message.content}"
            for message in messages
            if message.type == "human"
        ]
    )


base_llm = get_base_llm()


class ScoredListing(TypedDict):
    """Listing with relevancy and price scores."""

    listing: OlxSearchResult
    relevancy_score: int
    price_score: int
    combined_score: int


class State(TypedDict):
    """State for the agent."""

    # user-dependent variables
    messages: Annotated[list[BaseMessage], operator.add]  # chat history
    products: list[str]  # the products the user is interested in according to the llm
    include_configurations: bool  # whether to include related configurations (bundles which include the desired product)
    max_products_count: int  # the maximum number of products the user wants to see

    # agent-populated variables
    search_queries: list[str]  # the search queries to use to search for listings
    potential_listings: Annotated[
        list[OlxSearchResult], add_and_deduplicate_search_results
    ]  # all potential listings found by the search queries unfiltered
    filtered_listings: list[OlxSearchResult]
    # the listings that match the user's desired products according to the llm
    average_price: float  # the average price of the filtered listings
    median_price: float  # the median price of the filtered listings
    scored_listings: Annotated[
        list[ScoredListing], operator.add
    ]  # the listings that match the user's desired products according to the llm with scores
    # response removed; responses are appended as AI messages to messages
