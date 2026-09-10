# agent-service

Orchestrates the reasoning step of the LEDGER pipeline: retrieves evidence via
retrieval-api, reasons over it with an LLM (Llama 3.3 70B via Groq), and
returns a strict-schema, evidence-grounded answer. Never fabricates an answer —
on any failure (LLM error, malformed output, failed schema validation) it
retries once, then returns `insufficient_evidence` with the real reason.

## Structure

```
services/agent/
├── main.py              # FastAPI app, routes, lifespan (shared httpx client)
├── config.py             # env vars, LLM instantiation, retry/timeout policy
├── schemas.py             # request/response models incl. discriminated-union answer schema
├── tools.py                # async retrieval + safe arithmetic tools
├── validation.py            # validates LLM output against the answer schema
├── Dockerfile
├── requirements.txt
└── graph/
    ├── __init__.py
    ├── state.py                # AgentState TypedDict
    ├── nodes.py                 # retrieve / retry / reason nodes
    └── builder.py                 # compiles agent_graph (LangGraph StateGraph)
```

## Running

### Via Docker Compose (recommended)

This service is one of two started together — see `docker-compose.yml` at the
repo root. From the repo root:

```bash
echo "GROQ_API_KEY=your-groq-key" > .env
docker compose up --build
```

agent-service will be available at `http://localhost:8000`.

### Standalone (local dev, no Docker)

```bash
cd services/agent
pip install -r requirements.txt
cp .env.example .env   # fill in values, see below
python main.py            # serves on :8000
```

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GROQ_API_KEY` | Yes (for real answers) | — | Without it, every query returns `insufficient_evidence` ("LLM is not configured") instead of failing |
| `RETRIEVAL_SERVICE_URL` | No | `http://localhost:8001/api/v1/search/pipeline` | Must point at the hybrid+rerank pipeline endpoint. In Docker Compose this needs to be the container DNS name, e.g. `http://retrieval-service:8001/...`, once that service is added to the compose file |
| `RETRIEVAL_HTTP_TIMEOUT` | No | `8.0` | Seconds, per retrieval call |
| `LLM_MODEL_NAME` | No | `llama-3.3-70b-versatile` | |
| `LLM_TIMEOUT` | No | `20.0` | Seconds; bounds the LLM call itself |
| `MAX_RETRIEVAL_RETRIES` | No | `1` | Retries `retrieve` once if the initial search returns nothing |
| `MAX_LLM_ATTEMPTS` | No | `2` | 1 initial + 1 retry before falling back to `insufficient_evidence` |

**No API key / auth is required to call this service.** It was deliberately
left unauthenticated — this is a personal project running behind
docker-compose on a single host, not a multi-tenant deployment, so an
API-key layer was removed to avoid needless config drift between services.
If this ever gets deployed somewhere reachable by the public internet,
add auth back (e.g. a reverse proxy with basic auth, or reintroduce an
`X-API-Key` dependency) before exposing it.

## Endpoints

### `POST /api/v1/agent/query`

No auth required.

**Request**
```json
{ "question": "What was CTS's finished-goods balance in 2019?", "document_id": "doc_041" }
```

**Response** — one of `direct` / `calculated` / `multi_span` / `insufficient_evidence`, enforced structurally via a Pydantic discriminated union (see `schemas.py`). See `api-contract.md` → Strict Answer Schema for the full per-type shape.

**Errors** — `500` only for a truly unhandled exception. LLM/parse/validation failures do **not** 500 — they resolve to a `200` with `insufficient_evidence`.

### `GET /health`

Reports overall status plus per-dependency reachability — not a static `"ok"`.

```json
{
  "status": "ok | degraded",
  "service": "agent-service",
  "checks": {
    "llm_configured": true,
    "retrieval_service": true
  }
}
```

`status` is `degraded` if the LLM isn't configured or the retrieval service's `/health` isn't reachable. **Assumption to verify:** this derives the retrieval service's health-check URL by stripping the path after `/api/` from `RETRIEVAL_SERVICE_URL` — confirm retrieval-api actually exposes `GET /health` at that base path, or update the derivation in `main.py`.

## Design notes

- **No fabricated answers.** The old fallback (`"value": "Data retrieved from context"` on any LLM failure) was removed. Every failure path now surfaces truthfully as `insufficient_evidence` with a real `reason`, or as an HTTP error for truly unhandled exceptions.
- **Fully async.** All I/O (`httpx` for retrieval, `llm.ainvoke`, `agent_graph.ainvoke`) is non-blocking so the event loop isn't stalled during retrieval/LLM latency.
- **No `eval()`.** `calculate` uses a restricted AST walker (`tools.safe_arithmetic_eval`) supporting only numeric literals and `+ - * / % ** ()`.
- **Both retrieval tools are used.** `retrieve_node` runs `search_documents` and `search_tables` concurrently and merges/dedupes by `chunk_id` — previously `search_tables` was defined but never called.
- **Output is validated twice**: once structurally (Pydantic discriminated union as the route's `response_model`), once explicitly inside `reason_node` (`validate_answer`) before the LLM's output is trusted enough to return.
- **No authentication.** Intentional for this project's current scope (single-host docker-compose, not internet-facing). See the env var note above if that changes.