import json
from typing import Any, Dict, List
import logging
from typing_extensions import Optional

import requests
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

stage_to_description = {
    "parse_user_request": lambda data: "Planning search parameters",
    "generate_search_queries": lambda data: "Generating search queries",
    "search_for_listings": lambda data: f"Searching for {data['search_query']}",
    "filter_listings": lambda data: f"Filtering {data['listings_count']} listings",
    "score_listings": lambda data: f"Scoring {data['listings_count']} listings",
    "score_listings_progress": lambda data: f"Scoring {data['scored_listings_count']} of {data['total_listings_count']} listings",
    "generate_response": lambda data: "Generating response",
}


class Pipeline:
    class Valves(BaseModel):
        SERVER_URL: str = Field(
            default="http://localhost:8000",
            description="Base URL of the Agent server",
        )

    def __init__(self):
        self.name = "OLX Deal Finder"
        self.valves = self.Valves()

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        metadata = body.get("metadata", {})
        self.metadata = metadata
        return body

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict,
    ):
        # prevent sending openwebui tasks to the agent server
        if self.metadata.get("task", None) is not None:
            return

        messages = body.get("messages", [])

        try:
            with requests.post(
                f"{self.valves.SERVER_URL}/stream/openwebui",
                json={"messages": messages},
                stream=True,
                timeout=(10, 3600),
            ) as resp:
                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError:
                    yield from self._emit_http_error(resp)
                    return

                yield from self._stream_response(resp)

        except requests.exceptions.ConnectTimeout as exc:
            yield from self._emit_and_log_error(
                description="Connection timed out.",
                user_message="Timeout while connecting to the agent server. Ensure the server is running and reachable.",
                log_key="connect_timeout",
                exc=exc,
            )
        except requests.exceptions.ReadTimeout as exc:
            yield from self._emit_and_log_error(
                description="Request timed out.",
                user_message="The server took too long to respond after connecting. The request timed out.",
                log_key="read_timeout",
                exc=exc,
            )
        except requests.exceptions.ConnectionError as exc:
            yield from self._emit_and_log_error(
                description="Cannot connect to agent server.",
                user_message="Cannot connect to the agent server. Please verify the server is running and the URL is correct.",
                log_key="connection_error",
                exc=exc,
            )
        except requests.exceptions.RequestException as exc:
            yield from self._emit_and_log_error(
                description="Network error.",
                user_message="Network error while contacting the agent server. Please try again.",
                log_key="request_exception",
                exc=exc,
            )
        except Exception as exc:
            yield from self._emit_and_log_error(
                description="An unexpected error occurred.",
                user_message="An unexpected error occurred. Cannot reach agent server. Please check if the server is running and the URL is correct. Check logs for more details.",
                log_key="exception",
                exc=exc,
            )

    def _get_last_user_content(self, messages: List[Dict[str, Any]]) -> str:
        """Extract the most recent user message content from OpenWebUI-style messages."""
        for msg in reversed(messages or []):
            if msg.get("role") == "user":
                content = msg.get("content")
                return content

        return ""

    def _get_last_ai_content_from_response(self, response: dict) -> str:
        # {'messages': [{'content': '', 'additional_kwargs': {}, 'response_metadata': {}, 'type': 'ai', 'name': None, 'id': None, 'example': False, 'tool_calls': [], 'invalid_tool_calls': [], 'usage_metadata': None}]}
        for msg in reversed(response.get("messages", [])):
            if msg.get("type") == "ai":
                content = msg.get("content")
                return content

        return ""

    def _emit_status(self, description: str, done: bool):
        yield {
            "event": {
                "type": "status",
                "data": {"description": description, "done": done},
            }
        }

    def _emit_and_log_error(
        self, description: str, user_message: str, log_key: str, exc: Exception
    ):
        yield from self._emit_status(description, True)
        logger.exception(log_key, exc_info=exc)
        yield f"Error: {user_message}"

    def _emit_http_error(self, resp: requests.Response):
        status_code = resp.status_code
        description = f"Request failed with status {status_code}."
        error_message = f"Server responded with HTTP {status_code}."
        yield from self._emit_status(description, True)
        logger.error("http_error status=%s body_snippet=%s", status_code, resp.text)
        yield f"Error: {error_message}"

    def _stream_response(self, resp: requests.Response):
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                logger.debug({"line": line})
                try:
                    type, data = json.loads(line)
                except Exception:
                    logger.debug("invalid_json_line", {"line": line})
                    continue

                print(type)

                if type == "custom":
                    # stream final AI message content if present
                    if "messages" in data and data["messages"]:
                        last = data["messages"][-1]
                        # handle both dict-serialized messages and BaseMessage objects
                        if isinstance(last, dict):
                            last_type = last.get("type") or last.get("role")
                            if last_type == "ai" or last_type == "assistant":
                                logger.debug("found ai message", {"data": data})
                                yield last.get("content", "")
                        else:
                            if getattr(last, "type", None) == "ai":
                                logger.debug("found ai message", {"data": data})
                                yield getattr(last, "content", "")

                    elif data.get("stage") in stage_to_description:
                        description = stage_to_description[data["stage"]](data)

                        logger.debug(
                            "status", {"description": description, "done": False}
                        )
                        yield from self._emit_status(description, False)
                    elif "error" in data:
                        error_desc = data.get("error") or "Server reported an error."
                        yield from self._emit_status(error_desc, True)
                        logger.error("server_error_event %s", error_desc)
                        yield f"Error: {error_desc}"
                        return
                elif type == "updates" and "generate_response" in data:
                    yield from self._emit_status("Showing results", True)
                    yield self._get_last_ai_content_from_response(
                        data["generate_response"]
                    )

                else:
                    logger.debug(
                        "received unknown event, ignoring", {"type": type, "data": data}
                    )
        except requests.exceptions.RequestException as stream_exc:
            error_message = (
                "Connection lost during streaming from the server. Please retry."
            )
            yield from self._emit_status(error_message, True)
            logger.exception("streaming_request_exception", exc_info=stream_exc)
            yield f"Error: {error_message}"
