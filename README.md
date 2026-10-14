# News Search & Summary App

A **FastAPI + LangGraph RAG service** that accepts a natural-language news query,
retrieves relevant articles from Elasticsearch, and returns an AI-generated,
grounded summary together with the source articles that informed it.

This service is the **user-facing query layer** of a larger news-intelligence
pipeline (ingestion and indexing are handled by sibling services):

```
┌──────────────────────────┐   Kafka (Confluent)   ┌─────────────────────────────┐
│  news_fetch_scheduler    │ ────────────────────► │  news-consumer-ingester     │
│  • RSS / API ingestion   │                       │  • Full-article fetch       │
│  • Dedup (PostgreSQL)    │                       │  • Elasticsearch indexing   │
└──────────────────────────┘                       └──────────────┬──────────────┘
                                                                   │ Elasticsearch
                                                                   ▼  (news_articles)
                                                    ┌─────────────────────────────┐
                                                    │  news-summary-agent         │ ◄── THIS REPO
                                                    │  • Intent + category LLM    │
                                                    │  • Semantic/text search (ES)│
                                                    │  • gpt-4o-mini summary      │
                                                    │  • FastAPI  ·  port 8007    │
                                                    └─────────────────────────────┘
```

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Configuration](#configuration)
4. [Local Infrastructure Setup](#local-infrastructure-setup)
5. [Running the Application](#running-the-application)
6. [API Endpoints](#api-endpoints)
7. [Chat UI](#chat-ui)
8. [Testing & Code Quality](#testing--code-quality)
9. [Docker](#docker)
10. [Project Structure](#project-structure)
11. [Demo](#demo)
12. [Troubleshooting](#troubleshooting)

---

## Architecture

The request pipeline is a **LangGraph `StateGraph`** compiled with a
`PostgresSaver` checkpointer. The FastAPI lifespan builds the graph once at
startup, injecting a shared chat model, Elasticsearch client, and Postgres
connection; each request invokes the compiled graph.

```
POST /query ──► NewsInput ──► run_graph ──► graph.invoke
                                               │
                                               ▼
                                         ┌────────────┐
                                         │  classify  │  ClassifyIntent
                                         │            │  LLM → is_news_query,
                                         │            │  categories, fetch_latest
                                         └──────┬─────┘  (+ ES category check)
                                   is_news_query? │
                            ┌────────────────────┴───────────────────┐
                            │ false                                   │ true
                            ▼                                         ▼
                   ┌─────────────────┐                          ┌──────────┐
                   │ reply_off_topic │  Guard Rail #1           │  search  │  Search
                   └────────┬────────┘                          │          │  ES multi_match
                            │                                   └────┬─────┘  (+7-day filter &
                            │                      article_refs?     │         recency sort if
                            │                 ┌────────────────────┬─┘         fetch_latest)
                            │                 │ empty              │ found
                            │                 ▼                    ▼
                            │        ┌──────────────────┐    ┌───────────┐
                            │        │ reply_no_results │    │ summarize │  Summary
                            │        │  Guard Rail #2   │    │           │  ES mget + grounded
                            │        └────────┬─────────┘    └─────┬─────┘  cited LLM summary
                            └──────────────── ┴────────────────────┘
                                               ▼
                                   SummaryOk  ──►  QuerySuccessResponse
                                                    (or QueryFailedResponse on error)
```

**Two guard rails** keep the pipeline cheap and safe:

- **Guard Rail #1 (`reply_off_topic`)** — non-news queries never reach search or
  the summariser; the router `route_after_classify` sends them straight to a
  canned reply.
- **Guard Rail #2 (`reply_no_results`)** — if search returns no articles,
  `route_after_search` short-circuits to a canned reply instead of invoking the
  summarisation LLM with empty context.

**Checkpointing:** the `thread_id` is a `sha256` of the normalised query, backed
by `PostgresSaver`, so graph state is persisted per unique query.

### Nodes & key modules

| Module | Responsibility |
|--------|----------------|
| `src/api/app.py` | FastAPI app, routes, CORS, static mount, lifespan wiring |
| `src/graph/build_graph.py` | Assembles the `StateGraph` (nodes, routers, edges) and compiles it |
| `src/graph/run_graph_workflow.py` | Invokes the graph for one query; maps final state → API response |
| `src/nodes/classification.py` | `ClassifyIntent` — LLM intent/category extraction + ES category check |
| `src/nodes/search.py` | `Search` — builds & runs the Elasticsearch query, returns article refs |
| `src/nodes/summary.py` | `Summary` — `mget` article bodies, grounded cited summary via LLM |
| `src/channels/` | `TypedDict` state contracts (`NewsState`) + per-node result shapes & reducers |
| `src/data/` | Pydantic request/response models (`QueryRequest`, `QuerySuccessResponse`, …) |
| `src/adapters/` | `Elasticsearch`, chat model, Postgres, and FastAPI lifespan factories |
| `src/config/` | Application-config loader, logging setup, Vault secret loader |
| `static/chat-ui.html` | Self-contained browser chat interface (served at `/`) |

---

## Prerequisites

### Runtime

- **Python 3.12**
- [uv](https://docs.astral.sh/uv/) for dependency management (`pyproject.toml` + `uv.lock`)
- **Docker & Docker Compose** (for containerised runs)
- **Elastic Cloud / Elasticsearch 8.x** with a populated `news_articles` index
- **OpenAI API key** (`gpt-4o-mini`)
- Optional: a **LangSmith** account for tracing

### External services

| Service | Purpose | Default address |
|---------|---------|-----------------|
| **HashiCorp Vault** | Supplies runtime secrets (ES API key, OpenAI key, Postgres creds) as env vars at startup | `http://localhost:8200` |
| **PostgreSQL** | Backs the LangGraph `PostgresSaver` checkpointer | `localhost:5432` |
| **Elasticsearch** | Stores the `news_articles` index that search/summary read | Elastic Cloud |

---

## Configuration

Configuration is split into **three** places:

### 1. Bootstrap env vars (set externally per environment)

| Variable | Description |
|----------|-------------|
| `VAULT_ADDR` | Vault address (e.g. `http://localhost:8200`) |
| `VAULT_TOKEN` | Vault auth token |
| `VAULT_SECRET_PATH` | KV v2 path to read, e.g. `secret/CREDENTIALS` |

These are the **only** variables that must be set outside the app — everything
else is loaded from Vault or the YAML config.

### 2. Vault secrets (injected into environment variables)

Read from `VAULT_SECRET_PATH` at startup by `src/config/vault_secrets.py`:

| Secret key | Required | Description |
|------------|----------|-------------|
| `ELASTIC_READ_API_KEY` | Yes | Elasticsearch API key (read access) |
| `OPENAI_API_KEY` | Yes | OpenAI key for `gpt-4o-mini` |
| `POSTGRES_DB` | Yes | Checkpointer database name |
| `POSTGRES_USER` | Yes | Checkpointer database user |
| `POSTGRES_PASSWORD` | Yes | Checkpointer database password |
| `PG_HOST` / `PG_PORT` | No | Postgres host/port (default `localhost` / `5432`) |
| `LANGCHAIN_API_KEY` | No | LangSmith API key |
| `LANGCHAIN_TRACING_V2` | No | `"true"` to enable LangSmith tracing |
| `LANGCHAIN_PROJECT` | No | LangSmith project name |

### 3. Application config — `src/resources/application-config.yaml`

Non-secret settings loaded by `src/config/application_config.py`:

```yaml
ELASTIC_URL: "http://localhost:9200"   # Elasticsearch endpoint (non-secret)
request_timeout: 60
retry_on_timeout: True
max_retries: 3
http_compress: True
connections_per_node: 10
ES_INDEX: news_articles
CATEGORY_QUERY: { ... }                # template for the category-check query
SEARCH_QUERY_TEMPLATE: { ... }         # template for the article search query
```

### Elasticsearch index requirements

| Setting | Value |
|---------|-------|
| Index name | `news_articles` |
| Document `_id` | equal to the `article_id` field (summary retrieval uses `mget` by id) |
| Source fields | `article_id`, `title`, `content`, `source`, `published_at`, `link` |

---

## Local Infrastructure Setup

### 1 — Create the shared Docker networks

```bash
docker network create vault-network
docker network create services_network
```

### 2 — Start HashiCorp Vault and populate secrets

```bash
docker run -d \
  --name vault-server \
  --network vault-network \
  -p 8200:8200 \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=dev-root-token' \
  -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200' \
  hashicorp/vault:latest server -dev

export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=dev-root-token

vault kv put secret/CREDENTIALS \
  ELASTIC_READ_API_KEY="<your-elastic-read-api-key>" \
  OPENAI_API_KEY="<your-openai-api-key>" \
  POSTGRES_DB="newsdb" \
  POSTGRES_USER="news" \
  POSTGRES_PASSWORD="news" \
  PG_HOST="localhost" \
  PG_PORT="5432" \
  LANGCHAIN_API_KEY="<your-langsmith-api-key>" \
  LANGCHAIN_TRACING_V2="true" \
  LANGCHAIN_PROJECT="news-summary-agent"
```

> `ELASTIC_URL` is **not** a secret — set it in `application-config.yaml`.

### 3 — Start PostgreSQL (checkpointer backend)

```bash
docker run -d \
  --name postgres-server \
  --network services_network \
  -p 5432:5432 \
  -e POSTGRES_USER=news \
  -e POSTGRES_PASSWORD=news \
  -e POSTGRES_DB=newsdb \
  postgres:16-alpine
```

---

## Running the Application

### Option A — Local (uv virtualenv)

```bash
# 1. Create .venv and install runtime + dev dependencies from the lock file
uv sync

# 2. Set the Vault bootstrap variables
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=dev-root-token
export VAULT_SECRET_PATH=secret/CREDENTIALS

# 3. Start the server (run from the repo root so static/ resolves)
PYTHONPATH=src uv run uvicorn api.app:app --host 0.0.0.0 --port 8007 --reload
```

The API is then available at `http://localhost:8007`.

### Option B — Docker Compose

```bash
export VAULT_TOKEN=dev-root-token
docker compose up --build
```

Compose attaches the container to `vault-network` and `services_network`, points
`VAULT_ADDR` at `http://vault-server:8200`, and reads `VAULT_SECRET_PATH=secret/CREDENTIALS`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the Chat UI (`static/chat-ui.html`) |
| `GET` | `/health` | Liveness probe — returns `{"status": "ok"}` |
| `POST` | `/query` | Runs the full graph and returns a news summary |

### `POST /query` — request

```json
{ "query": "What are the latest developments in AI regulation?" }
```

### `POST /query` — success response (`status: "ok"`)

```json
{
  "query": "What are the latest developments in AI regulation?",
  "categories": ["technology", "ai", "politics"],
  "summary": "Regulators across the EU and US are accelerating AI oversight...",
  "articles": [
    {
      "title": "EU AI Act Enters Final Phase",
      "link": "https://eurotech.example.com/eu-ai-act",
      "source": "EuroTech",
      "published_at": "2026-03-28"
    }
  ],
  "duration_seconds": 2.341,
  "status": "ok"
}
```

### `POST /query` — failure response (`status: "failed"`)

```json
{
  "query": "...",
  "error": "RuntimeError: ...",
  "error_code": 500,
  "status": "failed"
}
```

### Interactive API docs

- **Swagger UI:** `http://localhost:8007/docs`
- **ReDoc:** `http://localhost:8007/redoc`

---

## Chat UI

A self-contained single-page chat interface is bundled at `static/chat-ui.html`
and served at the root path `/`.

```
http://localhost:8007/
```

The page POSTs queries to `http://127.0.0.1:8007/query`, so the FastAPI server
must be running (whether the page is opened via the server or directly from disk).

**Features:** terminal-style dark theme, Markdown rendering, an animated typing
indicator, structured responses (summary / categories / source articles /
duration), and `Enter` to send · `Shift+Enter` for a newline.

---

## Testing & Code Quality

Dev tooling (`pytest`, `pytest-cov`, `mypy`) is installed by `uv sync`.

```bash
# Run the full test suite (config is pinned in pytest.ini: pythonpath=src, *_test.py)
uv run pytest

# A single module
uv run pytest tests/nodes/search_test.py -v

# Coverage
uv run pytest --cov=src --cov-report=term-missing

# Static type check
uv run mypy src

# Lint / format (ruff) and the configured pre-commit hooks
uv run ruff check src
uv run pre-commit run --all-files
```

The suite uses **fakes, not live services**: a `FakeListChatModel` for the LLM, a
`MagicMock`/`MemorySaver` for Elasticsearch and the checkpointer, and FastAPI
dependency overrides — so no Vault, Elasticsearch, OpenAI, or Postgres is needed.

### Test layout (mirrors `src/`)

```
tests/
├── conftest.py                 # config load + fake-LLM / mock-ES factories
├── channels/news_state_test.py # state reducers (merge/dedupe/append)
├── nodes/                      # classification, search, summary nodes
├── graph/                      # routers, end-to-end routing, state→response mapping
├── config/                     # application config + Vault secret loader
├── adapters/                   # Elasticsearch + chat-model factories
├── data/                       # Pydantic response models
└── api/app_test.py             # endpoints via Starlette TestClient
```

---

## Docker

### Build

```bash
docker build -t news-summary-agent:latest .
```

The two-stage Dockerfile installs locked runtime deps with
`uv sync --frozen --no-dev --no-install-project` into `/app/.venv`, then copies
that venv into a slim runtime image that runs as a non-root `appuser` with
`PYTHONPATH=src` and **exposes port 8007**. Because only `pyproject.toml` and
`uv.lock` are copied before the dependency install, source edits don't bust the
dependency layer. After `uv add`/`uv remove`, commit both files — `--frozen`
fails the build on a stale lock.

### Run standalone

```bash
docker run -d \
  --name news-summary-agent \
  --network vault-network \
  --network services_network \
  -p 8007:8007 \
  -e VAULT_ADDR=http://vault-server:8200 \
  -e VAULT_TOKEN=dev-root-token \
  -e VAULT_SECRET_PATH=secret/CREDENTIALS \
  news-summary-agent:latest
```

### Compose

```bash
export VAULT_TOKEN=dev-root-token
docker compose up --build -d

docker compose logs -f app   # service name is `app`
docker compose down
```

The `app` service restarts `unless-stopped` and runs a healthcheck every 60 s
against `GET /health`.

---

## Project Structure

```
news-summary-agent/
├── demo/                              # Screenshots and screen recordings
├── src/
│   ├── adapters/
│   │   ├── elasticsearch.py           # Cached Elasticsearch client factory
│   │   ├── llm.py                     # Cached chat-model factory (gpt-4o-mini)
│   │   ├── postgres.py                # Postgres connection for the checkpointer
│   │   └── lifespan.py                # FastAPI lifespan — builds & injects the graph
│   ├── api/
│   │   └── app.py                     # FastAPI application and routes
│   ├── channels/                      # TypedDict state contracts + reducers
│   │   ├── news_state.py              # NewsState (shared graph state)
│   │   ├── article_reference.py       # ArticleReference (id + score)
│   │   ├── article_hit.py             # ArticleHit (displayable metadata)
│   │   ├── category_search_results.py # ClassifyIntent output
│   │   ├── search_results.py          # Search output
│   │   ├── summary_result.py          # Summary / guard-rail output
│   │   └── summary_ok.py              # Graph output schema
│   ├── config/
│   │   ├── application_config.py      # YAML config loader (get_config)
│   │   ├── logging_setup.py           # Logging configuration
│   │   └── vault_secrets.py           # Vault KV v2 → os.environ
│   ├── data/                          # Pydantic request/response models + seed replies
│   ├── graph/
│   │   ├── build_graph.py             # StateGraph assembly + routers
│   │   └── run_graph_workflow.py      # Invoke graph → map to API response
│   ├── nodes/
│   │   ├── classification.py          # ClassifyIntent node
│   │   ├── search.py                  # Search node
│   │   └── summary.py                 # Summary node
│   ├── resources/
│   │   ├── application-config.yaml    # Non-secret app config
│   │   └── logging_config.json        # Logging dictConfig
│   └── main.py                        # Standalone uvicorn entry point (port 8007)
├── static/
│   └── chat-ui.html                   # Browser chat interface (served at /)
├── tests/                             # pytest suite mirroring src/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml                     # Dependencies (runtime + dev) and mypy config
├── pytest.ini
└── uv.lock                            # Resolved, pinned dependency set
```

CI runs via GitHub Actions (`.github/workflows/ci-cd-yml`) with a secret scan
(`.github/workflows/gitleaks.yml`).

---

## Demo

Screenshots and recordings live in `demo/`:

| File | Description |
|------|-------------|
| `demo/user_chat_interaction_live_session.webm` | End-to-end recording: startup → query → response |
| `demo/services_running_on_locale_docker.png` | Services running in local Docker |
| `demo/user_chat_interaction_logs.png` | Chat interaction logs |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `RuntimeError: ELASTIC_URL and ELASTIC_READ_API_KEY must be set` | Vault secrets not loaded / `ELASTIC_URL` missing from YAML | Check `VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_SECRET_PATH` and `application-config.yaml` |
| `ValueError: VAULT_ADDR and VAULT_TOKEN must be set` | Bootstrap env vars missing | Export `VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_SECRET_PATH` |
| Startup `RuntimeError: ping returned False` | Elasticsearch unreachable | Verify the ES endpoint, API key, and connectivity |
| App can't connect to Postgres on startup | Checkpointer DB unreachable / creds wrong | Check `POSTGRES_*` secrets and that Postgres is on `services_network` |
| Docker run fails: network not found | Shared networks missing | `docker network create vault-network && docker network create services_network` |
| Chat UI shows "Could not reach the server" | App not running or wrong port | Start the server on port **8007** |
| LangSmith traces not appearing | Tracing env not set | Set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in Vault |

---

## Author

Srini Yedluri
