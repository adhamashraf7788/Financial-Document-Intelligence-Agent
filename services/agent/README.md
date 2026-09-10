# agent-service (Reasoning "Brain" Service)

LangGraph-based reasoning agent. Routes a question through retrieval,
decides whether evidence is sufficient (retrying once if not), reasons
over retrieved evidence with an LLM, and returns a schema-compliant
answer.

## Endpoint

```
POST /api/v1/agent/query
Content-Type: application/json
Body: { "question": "...", "document_id": "..." }   // document_id optional, corpus-wide if omitted
```

Returns a `StructuredAgentOutput`: `{ answer_type, evidence, params }`,
matching the strict answer schema in `shared/schemas.py`.

```
GET /health
```
Basic health check.

## How it works

1. **`retrieve`** — calls `search_documents` (real HTTP call to
   `retrieval-api`'s search pipeline via `RETRIEVAL_SERVICE_URL`).
2. **Conditional branch** — if nothing came back and this is the first
   attempt, retries retrieval once (`prepare_retry` → back to
   `retrieve`); otherwise proceeds to reasoning.
3. **`reason`** — if no evidence was found after the retry, returns
   `insufficient_evidence`. Otherwise, sends the retrieved evidence and
   question to the LLM (Groq's `llama-3.3-70b-versatile`), which
   returns a structured answer. If the answer type is `calculated`, the
   formula is re-run through the deterministic `calculate()` tool
   rather than trusting the LLM's own arithmetic.
4. If the LLM call or JSON parsing fails, falls back to a simple
   `direct` answer built from the raw retrieved evidence, so the
   service degrades gracefully instead of erroring out.

## Environment variables

```
GROQ_API_KEY=...                # required for real LLM reasoning
RETRIEVAL_SERVICE_URL=http://<retrieval-host>/api/v1/search/pipeline
```

Without `GROQ_API_KEY` set, the agent still runs (retrieval + the
conditional graph work), but skips straight to the raw-evidence
fallback answer instead of LLM reasoning.

## Running it

**Directly:**
```bash
cd services/agent
pip install -r requirements.txt
cd ../..
uvicorn services.agent.main:app --port 8000
```

**In Docker:**
```bash
# from the project root
docker build -t agent-service -f services/agent/Dockerfile .
docker run --env-file services/agent/.env -p 8000:8000 agent-service
```

⚠️ Same `.env` quoting rule as the other services: `docker run
--env-file` does not strip surrounding quotes the way Python's
`load_dotenv()` does. Keep values unquoted, e.g.
`GROQ_API_KEY=gsk_xxxxxxxx`, not `GROQ_API_KEY="gsk_xxxxxxxx"`.

## Testing

```bash
python -m pytest services/agent/tests/test_agent.py -v
```

Covers the health check, the `calculate()` tool's arithmetic, and a
full round-trip through `/api/v1/agent/query`.

## For orchestrator-api / integration

- `POST http://<agent-host>:8000/api/v1/agent/query`
- Response is already schema-compliant — safe to forward directly to
  `answer-validator-api`'s `/validate_answer`.
- Depends on `retrieval-api` being reachable at `RETRIEVAL_SERVICE_URL`;
  if it's down, retrieval returns empty and the agent will correctly
  answer `insufficient_evidence` rather than fail outright.
