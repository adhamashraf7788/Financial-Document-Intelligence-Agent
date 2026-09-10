# ui-service (Gradio UI)

Two-tab Gradio interface: a chat view for corpus-wide questions, and a
dashboard showing indexed documents and recent query logs.

## Tabs

- **Financial Assistant** — ask a question (optionally scoped to a
  `document_id`), see the formatted answer with source citations, and
  the full raw JSON response for debugging.
- **Corpus Dashboard** — indexed document list and recent query log.

## Data sources (in priority order)

1. Real orchestrator data — `GET {ORCHESTRATOR_SERVICE_URL}/api/v1/dashboard`
2. `mock-data/ui_service_mock.json`, if orchestrator is unreachable
3. Hardcoded fallback values, if even the mock file is missing

Same fallback pattern for chat: tries `POST
{ORCHESTRATOR_SERVICE_URL}/api/v1/query` first, falls back to a
keyword-based mock response generator if the orchestrator call fails.

**This means the UI will run and look functional even with no other
service up** — useful for isolated UI testing, but worth remembering
during integration testing that a "successful-looking" answer might
actually be the mock fallback, not a real orchestrator response. Check
the raw JSON panel or server logs if in doubt.

## Environment variables

```
ORCHESTRATOR_SERVICE_URL=http://<orchestrator-host>:8000   # defaults to http://localhost:8000
GRADIO_SHARE=false                                          # set "true" to enable a public Gradio tunnel link
```

`GRADIO_SHARE` defaults to `false` — a public tunnel is opt-in, not
automatic.

## Running it

**Directly:**
```bash
cd services/ui
pip install -r requirements.txt
python app.py
```
Opens on `http://localhost:7860`.

**In Docker:**
```bash
# from the project root
docker build -t ui-service -f services/ui/Dockerfile .
docker run -p 7860:7860 -e ORCHESTRATOR_SERVICE_URL=http://<host>:8000 ui-service
```

## Testing

No dedicated test file yet — `pytest` is listed in requirements but
`services/ui/tests/` doesn't currently exist. Manual verification: load
both tabs, submit a question, click Refresh on the dashboard.

## For orchestrator-api / integration

- Expects `GET /api/v1/dashboard` (indexed docs + recent queries) and
  `POST /api/v1/query` (question in, schema-compliant answer out) on
  orchestrator.
- No direct dependency on agent-service, retrieval-api, or validator —
  UI only ever talks to orchestrator.
