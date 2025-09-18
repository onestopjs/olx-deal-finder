"""Generate search queries for OLX based on user request."""

import logging

from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate

from .common import State, base_llm
from langgraph.config import get_stream_writer
from .settings import settings


class SearchQueries(BaseModel):
    """Search queries for OLX."""

    search_queries: list[str]


search_queries_prompt = PromptTemplate.from_template("""You are generating search queries for the Bulgarian second-hand marketplace OLX.

Rules:
- Output ONLY product search queries (no explanations).
- Do NOT add clarifiers like "used", "second-hand", etc.
- Generate 3–5 distinct queries for each product, using common variations, synonyms, or spelling differences as they might appear in OLX.
- If applicable, descriptors must be in Bulgarian.

Products to generate queries for:
{products}
""")

search_queries_llm = base_llm.with_structured_output(
    SearchQueries,
    method="json_schema" if not settings.tool_calling_enabled else "function_calling",
)


logger = logging.getLogger(__name__)


def generate_search_queries(state: State) -> State:
    """Generate search queries for OLX based on user request."""

    writer = get_stream_writer()
    writer({"stage": "generate_search_queries"})

    prompt = search_queries_prompt.invoke({"products": state["products"]})
    response = search_queries_llm.invoke(prompt)

    logger.info(
        "generated search queries", extra={"count": len(response.search_queries)}
    )
    return {"search_queries": response.search_queries}
