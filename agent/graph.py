"""Graph for the OLX deal finder agent."""

import logging

from langgraph.graph import END, START, StateGraph

from .common import State
from .filter_listings import filter_listings
from .generate_search_queries import generate_search_queries
from .generate_response import generate_response
from .parse_user_request import parse_user_request
from .score_listings import score_listings
from .search_for_listings import search_for_listings, should_continue_searching
from .settings import settings
from .logging_config import configure_logging

configure_logging(settings.log_level)

graph = StateGraph(State)

graph.add_node("parse_user_request", parse_user_request)
graph.add_edge(START, "parse_user_request")

graph.add_node("generate_search_queries", generate_search_queries)
graph.add_edge("parse_user_request", "generate_search_queries")

graph.add_edge("generate_search_queries", "search_for_listings")
graph.add_node("search_for_listings", search_for_listings)
graph.add_conditional_edges(
    "search_for_listings",
    should_continue_searching,
    {
        "search_for_listings": "search_for_listings",
        "continue": "filter_listings",
    },
)

graph.add_node("filter_listings", filter_listings)
graph.add_edge("filter_listings", "score_listings")

graph.add_node("score_listings", score_listings)
graph.add_edge("score_listings", "generate_response")


graph.add_node("generate_response", generate_response)
graph.add_edge("generate_response", END)


olx_deal_finder = graph.compile()
