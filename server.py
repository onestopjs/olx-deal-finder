import json
import logging
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from typing import List
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    SystemMessage,
)

from agent.logging_config import configure_logging
from agent.graph import olx_deal_finder


configure_logging()
logger = logging.getLogger(__name__)
app = FastAPI()


class Input(BaseModel):
    messages: List[dict] = Field(
        ..., description="List of message dicts with role/content"
    )


def _coerce_message(m: dict) -> BaseMessage:
    t = m.get("type") or m.get("role")
    content = m.get("content", "")
    if t in ("human", "user"):
        return HumanMessage(content=content)
    if t in ("ai", "assistant"):
        return AIMessage(content=content)
    if t in ("system",):
        return SystemMessage(content=content)
    # default to human
    return HumanMessage(content=content)


async def stream_openwebui_agent(input: Input):
    messages: List[BaseMessage] = [_coerce_message(m) for m in input.messages]
    async for chunk in olx_deal_finder.astream(
        {"messages": messages}, stream_mode=["updates", "custom"]
    ):
        yield json.dumps(jsonable_encoder(chunk)) + "\n"


async def stream_agent(input: Input):
    messages: List[BaseMessage] = [_coerce_message(m) for m in input.messages]
    async for chunk in olx_deal_finder.astream(
        {"messages": messages}, stream_mode=["values"]
    ):
        yield json.dumps(jsonable_encoder(chunk)) + "\n"


async def invoke_agent(input: Input):
    messages: List[BaseMessage] = [_coerce_message(m) for m in input.messages]
    response_state = olx_deal_finder.invoke({"messages": messages})

    # return last AI message content if present
    last_ai = None
    for message in reversed(response_state.get("messages", [])):
        if getattr(message, "type", None) == "ai":
            last_ai = message
            break

    return last_ai.content if last_ai else ""


@app.post("/stream/openwebui")
async def stream_openwebui(input: Input):
    logger.info(
        "/stream/openwebui called", extra={"messages_count": len(input.messages)}
    )
    return StreamingResponse(
        stream_openwebui_agent(input), media_type="application/x-ndjson"
    )


@app.post("/stream")
async def stream(input: Input):
    logger.info("/stream called", extra={"messages_count": len(input.messages)})
    return StreamingResponse(stream_agent(input), media_type="application/x-ndjson")


@app.post("/invoke")
async def invoke(input: Input):
    logger.info("/invoke called", extra={"messages_count": len(input.messages)})
    return jsonable_encoder(invoke_agent(input))
