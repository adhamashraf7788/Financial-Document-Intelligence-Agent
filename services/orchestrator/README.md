# Orchestrator Service

The Orchestrator Service is the main API entry point for the LEDGER Financial Document Intelligence pipeline. It receives user questions, forwards them to the Agent Service, validates the returned structured answer, and exposes dashboard statistics.

The Orchestrator is responsible for coordinating services rather than performing retrieval or reasoning itself.

## Responsibilities

The Orchestrator Service:

* Receives questions from the frontend/UI.
* Accepts an optional `document_id` to limit a query to a specific document.
* Sends requests to the Agent Service.
* Passes the API key to the Agent Service when provided.
* Measures query latency.
* Returns a strict structured response.
* Provides a health-check endpoint.
* Provides dashboard statistics and recent-query information.

The Agent Service remains responsible for retrieval, reasoning, and generating the final evidence-grounded answer.

---

## Project Structure

```text
services/orchestrator/
│
├── main.py
├── orchestrator.py
├── clients.py
├── models.py
├── config.py
├── requirements.txt
├── Dockerfile
│
└── tests/
    ├── test_clients.py
    └── test_orchestrator.py
```

---

## File Description

### `main.py`

Defines the FastAPI application and the public API endpoints.

Endpoints:

```text
GET  /health
POST /api/v1/query
GET  /api/v1/dashboard
```

`main.py` also handles optional API-key authentication using the `X-API-Key` request header.

The `/api/v1/query` endpoint receives a `QueryRequest`, sends it to the Orchestrator, and returns a `StructuredAgentOutput`.

---

### `orchestrator.py`

Contains the main orchestration logic.

The `Orchestrator` class:

* Calls the Agent Service through `AgentClient`.
* Measures request latency.
* Tracks the total number of queries.
* Tracks total query latency.
* Calculates average latency.

The global `orchestrator` instance is used by the FastAPI application.

---

### `clients.py`

Contains the HTTP client used to communicate with the Agent Service.

`AgentClient` provides:

```text
query()
health()
```

`query()` sends:

```json
{
  "question": "What is the revenue?",
  "document_id": "doc_017"
}
```

to:

```text
/api/v1/agent/query
```

The client uses `httpx.AsyncClient` for asynchronous communication.

---

### `models.py`

Contains the Pydantic models used by the Orchestrator API.

Main models include:

* `QueryRequest`
* `Evidence`
* `AnswerParams`
* `StructuredAgentOutput`
* `DashboardStats`
* `IndexedDocument`
* `RecentQuery`
* `DashboardResponse`

These models ensure that requests and responses follow the project's API contract.

---

### `config.py`

Contains environment-based configuration for the Orchestrator.

Important settings include:

```text
AGENT_URL
RETRIEVAL_URL
RERANKER_URL
DOC_PROCESSOR_URL
VALIDATOR_URL
ORCHESTRATOR_API_KEY
ORCHESTRATOR_REQUEST_TIMEOUT
```

The default Agent Service URL is:

```text
http://agent:8000
```

For local development, `AGENT_URL` can be changed to the local Agent Service address.

Example:

```powershell
$env:AGENT_URL="http://127.0.0.1:8001"
```

---

### `requirements.txt`

Contains the Python dependencies required by the Orchestrator:

```text
fastapi
uvicorn[standard]
httpx
pydantic
```

---

### `Dockerfile`

Defines the container image for the Orchestrator Service.

The Docker image:

1. Uses Python 3.11.
2. Installs the required dependencies.
3. Copies the Orchestrator source code.
4. Copies the shared project code.
5. Exposes port `8000`.
6. Starts the FastAPI application using Uvicorn.

---

## Tests

The Orchestrator includes tests for:

### Agent Client

`tests/test_clients.py`

Tests:

* Agent query requests.
* Agent health checks.
* HTTP client behavior using mocked responses.

### Orchestrator

`tests/test_orchestrator.py`

Tests:

* Structured query responses.
* Average latency initialization.
* `/api/v1/query`.
* Request validation when the question is missing.

Run all Orchestrator tests from the repository root:

```powershell
python -m pytest services/orchestrator/tests -v
```

Expected result:

```text
6 passed
```

---

## API

### Query

```text
POST /api/v1/query
```

Request:

```json
{
  "question": "What is the revenue?",
  "document_id": "doc_017"
}
```

Response:

```json
{
  "answer_type": "direct",
  "evidence": [
    {
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement"
    }
  ],
  "params": {
    "value": "100",
    "formula": null,
    "values": null,
    "reason": null
  }
}
```

Possible answer types include:

```text
direct
calculated
multi_span
insufficient_evidence
```

---

## Health Check

```text
GET /health
```

Example:

```json
{
  "status": "ok",
  "service": "orchestrator-service",
  "checks": {
    "agent_service": true
  }
}
```

The Orchestrator reports `degraded` if the Agent Service cannot be reached.

---

## Dashboard

```text
GET /api/v1/dashboard
```

Returns:

* Number of indexed documents.
* Number of tables.
* Average query latency.
* Indexed document information.
* Recent queries.

Example:

```json
{
  "dashboard_stats": {
    "indexed_documents": 0,
    "total_tables": 0,
    "avg_latency_ms": 347.9
  },
  "indexed_documents": [],
  "recent_queries": []
}
```

The current implementation tracks average query latency. Document and recent-query lists are currently returned as empty lists until their corresponding tracking/indexing functionality is connected.

---

## Running Locally

From the repository root:

```powershell
$env:AGENT_URL="http://127.0.0.1:8001"
python -m uvicorn services.orchestrator.main:app --reload --port 8000
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## Service Communication

The basic request flow is:

```text
Frontend / UI
      │
      ▼
Orchestrator
      │
      ▼
Agent Service
      │
      ├── Retrieval
      ├── Reasoning / LLM
      └── Structured Answer
      │
      ▼
Orchestrator
      │
      ▼
Frontend / UI
```

The Orchestrator does not duplicate the retrieval or reranking logic handled by the Agent Service.

---

## Error Handling

If the Agent Service returns an unsuccessful HTTP response, the Orchestrator returns an HTTP `500` error.

If the Agent Service cannot be reached, the query also fails and the error is returned through the Orchestrator API.

The Agent Service itself is responsible for returning `insufficient_evidence` when it cannot produce a valid evidence-grounded answer.

---

## Current Verification

The Orchestrator Service has been tested with:

```text
6 tests passed
```

The following were also verified manually through Swagger:

```text
GET  /health          ✓
POST /api/v1/query   ✓
GET  /api/v1/dashboard ✓
```

The Orchestrator successfully communicated with the Agent Service during local testing.
