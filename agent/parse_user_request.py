"""Parse user request into structured data."""

import logging

from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate

from .common import State, base_llm, get_history_summary
from .settings import settings


class UserRequest(BaseModel):
    """User request for which products they are interested in and how many final listings they want to see."""

    products: list[str] = Field(
        description="The products the user is interested in", default=None
    )
    max_products_count: int = Field(
        description="The maximum number of products the user is interested in. If not provided, default to 20",
        default=20,
    )
    include_configurations: bool = Field(
        description="Whether to include configurations which include the desired product, or only the desired product with nothing else.",
        default=False,
    )


user_request_prompt = PromptTemplate.from_template("""
Extract the following fields from the user request and return them strictly in the schema provided.

Important:
- "products" must only contain actual items the user wants to buy (e.g., "iPhone 14", "Google Pixel 9 Pro XL").
- Do NOT treat colors, sizes, storage, conditions (e.g. "hazel", "128GB", "new") as products. 
  Those are filters/attributes, not standalone products.
- If the user mentions only filters without restating the product, assume they apply to the previously requested product.

Schema fields:
- products: list of products the user is interested in (strings).
- max_products_count: integer. If not specified, set to 20.
- include_configurations: boolean. If not specified, set to False. 
  True = include related configurations (bundles or variations), 
  False = only the exact product.

User request:
{prompt}
""")


user_request_llm = base_llm.with_structured_output(
    UserRequest,
    method="json_schema" if not settings.tool_calling_enabled else "function_calling",
)


logger = logging.getLogger(__name__)


def parse_user_request(state: State) -> State:
    """Parse user request into structured data."""
    logger.debug("parse_user_request input", extra={"state_keys": list(state.keys())})

    writer = get_stream_writer()
    writer({"stage": "parse_user_request"})

    user_prompt = get_history_summary(state["messages"])
    prompt = user_request_prompt.invoke({"prompt": user_prompt})
    user_request = user_request_llm.invoke(prompt)

    logger.info(
        "parsed user request",
        extra={
            "products": user_request.products,
            "max_products_count": user_request.max_products_count,
            "include_configurations": user_request.include_configurations,
        },
    )
    return {
        "products": user_request.products,
        "max_products_count": user_request.max_products_count,
        "include_configurations": user_request.include_configurations,
    }
