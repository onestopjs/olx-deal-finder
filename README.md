# OLX Deal Finder

This is simple LangGraph agent that tries to find the best deals on OLX.bg for a specific product. It comes with a FastAPI server, a Dockerfile, and OpenWebUI pipeline.

Works with Ollama, OpenAI, and Anthropic, although more providers can easily be added. It is recommended to choose a good instruction-following model.

## Usage (TL;DR)

## Set Up Environment

Copy .env.example to .env and fill in the required values.

### Run Server

The recommended way to use the server is to run the Docker container. You can use the pre-built image:

```bash
docker run -p 8000:8000 --env-file .env ghcr.io/onestopjs/olx-deal-finder:latest
```

### Make a Request

Then make a request to the server:

```bash
curl -X POST http://localhost:8000/invoke -H "Content-Type: application/json" -d '{"messages": [{"type": "human", "content": "I want to buy an rtx 3090"}]}'
```

### Stream a Response

Or stream the response:

```bash
curl -X POST http://localhost:8000/stream -H "Content-Type: application/json" -d '{"messages": [{"type": "human", "content": "I want to buy an rtx 3090"}]}'
```

## Technical Details

### OLX API

The agent uses the OLX GraphQL gateway to search for listings. It is limited to one request per seconds so that we don't abuse the API.

OLX does provide developer access, but it does not support searching for listings. If anyone from the OLX team has concerns about this usage, please reach out and I'll be happy to discuss alternative approaches.

### LangGraph Agent Architecture

This project uses a LangGraph state machine to turn a short user request into a structured marketplace search and a concise market summary. The graph is compiled in `agent/graph.py` and the server renders a diagram to `graph.png` at startup.

#### Node flow

- **START → parse_user_request**: Extracts `products`, `max_products_count`, and `include_configurations` from chat history using a structured LLM call.
- **generate_search_queries**: Expands `products` into diverse OLX-ready `search_queries` (3–5 per product, Bulgarian terms where relevant).
- **search_for_listings (loop)**: Pops the next query, fetches up to `settings.max_pages_to_search` pages via OLX GraphQL, accumulates `potential_listings`, and loops while queries remain.
- **filter_listings**: Uses an LLM to keep only listings relevant to the desired products. Computes `average_price` and `median_price` over priced items.
- **score_listings**: For each filtered listing, computes a relevance score with an LLM and a normalized price score against the median; combines them into `combined_score`.
- **generate_response → END**: Produces a short market summary in English and appends a bulleted list of the top listings (markdown optional).

#### State shape (selected keys)

The graph carries a single state object (see `agent/common.py` for full typing):

- **messages**: chat history (LangChain messages)
- **products**: list[str]
- **include_configurations**: bool
- **max_products_count**: int
- **search_queries**: list[str]
- **potential_listings**: list[OlxSearchResult] (deduplicated across searches)
- **filtered_listings**: list[OlxSearchResult]
- **average_price / median_price**: float
- **scored_listings**: list[{ listing, relevancy_score, price_score, combined_score }]

#### Streaming and observability

Each node writes structured events to the stream (via `langgraph.config.get_stream_writer()`), enabling live progress UIs:

Server endpoints in `server.py`:

- `POST /invoke`: returns the final summarized AI message.
- `POST /stream`: NDJSON stream of state values.
- `POST /stream/openwebui`: NDJSON stream of updates suitable for the OpenWebUI pipeline.

#### Key settings

- **llm_provider**: `ollama` | `openai` | `anthropic` and corresponding creds/model fields
- **tool_calling_enabled**: switch between JSON schema and function-calling
- **relevancy_score_weight / price_score_weight / relevancy_gamma**: scoring behavior
- **max_pages_to_search**: pagination depth per query
- **listings_batch_size**: batch size for LLM filtering
- **enable_markdown**: render links with markdown
- **debug_scoring**: include score details in listing titles
- **log_level**: logging verbosity

Tip: Copy `.env.example` to `.env` and set provider-specific variables (API keys, models, URLs). The agent selects the correct LLM client based on `llm_provider`.
