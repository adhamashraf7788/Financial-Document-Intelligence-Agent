# ui-service

Gradio front-end for LEDGER: a query interface that calls agent-service
directly (no orchestrator-service exists yet), plus a corpus dashboard that
currently always falls back to mock data since the dashboard endpoint hasn't
been built anywhere yet. Every response is labeled by its real source
(`live`, `mock`, or `error`) — a failed backend call is never silently
rendered as if it were a real, evidence-backed answer.

## Structure

```
services/ui/
├── app.py             # Gradio Blocks UI, async handlers, live/mock/error labeling
├── config.py            # env vars
├── api_client.py          # async httpx calls to agent-service
├── mock_fallback.py         # demo/mock data + heuristic mock answer generator
├── formatting.py              # answer + citation formatting, source banners
├── Dockerfile
└── requirements.txt
```

## Running

### Via Docker Compose (recommended)

Started together with agent-service — see `docker-compose.yml` at the repo
root. From the repo root:

```bash
echo "GROQ_API_KEY=your-groq-key" > .env
docker compose up --build
```

ui-service will be available at `http://localhost:7860`. Inside the compose
network it talks to agent-service via the container DNS name
`http://agent-service:8000`, already set as the default
`ORCHESTRATOR_SERVICE_URL` in `docker-compose.yml`.

### Standalone (local dev, no Docker)

```bash
cd services/ui
pip install -r requirements.txt
cp .env.example .env   # fill in values, see below
python app.py            # serves on :7860
```

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ORCHESTRATOR_SERVICE_URL` | No | `http://localhost:8000` | Base URL only — paths are appended in `api_client.py`. **Currently points directly at agent-service** since orchestrator-service doesn't exist yet; see note below |
| `UI_QUERY_TIMEOUT` | No | `15.0` | Seconds |
| `UI_DASHBOARD_TIMEOUT` | No | `3.0` | Seconds |
| `UI_ALLOW_MOCK_FALLBACK` | No | `True` | If `false`, a failed backend call shows a plain error instead of a labeled mock answer |
| `MOCK_UI_PATH` | No | `../mock-data/ui_service_mock.json` (relative to `services/ui/`) | Dashboard mock data source when the backend is unreachable |
| `GRADIO_SHARE` | No | `False` | Passed to `demo.launch(share=...)` |

**No API key is sent or required.** Auth was intentionally removed on both
sides (see agent-service's README) to keep this simple for a
single-host, non-public docker-compose setup.

## ⚠️ Temporary wiring, until orchestrator-service exists

- `ORCHESTRATOR_QUERY_PATH` in `config.py` is currently set to
  `/api/v1/agent/query` — agent-service's **real** path — not the originally
  planned `/api/v1/query`, since there's no orchestrator to proxy that yet.
- `/api/v1/dashboard` doesn't exist anywhere yet. The **Corpus Dashboard tab
  will always show mock data** until an orchestrator (or agent-service
  itself) implements it.
- Once orchestrator-service is built: point `ORCHESTRATOR_SERVICE_URL` at it
  instead of agent-service, and flip `ORCHESTRATOR_QUERY_PATH` back to
  `/api/v1/query`.

## Behavior on backend failure

| Scenario | `UI_ALLOW_MOCK_FALLBACK=True` (default) | `UI_ALLOW_MOCK_FALLBACK=False` |
|---|---|---|
| Backend unreachable / non-200 / timeout | Shows a heuristic mock answer with a visible `⚠️ Demo mode` banner and `[mock]` suffix on the answer type | Shows `❌ Request failed: <error>`, no fabricated answer |
| Dashboard call (always fails right now) | Loads `mock-data/ui_service_mock.json` (or an inline default), stat labels suffixed `(mock)` | Empty dashboard, stat labels suffixed `(error)` |

Mock answers use the same Strict Answer Schema shape as real ones but are
always visibly labeled — `calculated` mock answers explicitly mark their
`formula` as `"(mock — not computed from real evidence)"` rather than
echoing the raw question as if it were a real formula.

## Design notes

- **Fully async.** `api_client.py` uses `httpx.AsyncClient`; both Gradio handlers are `async def`.
- **Consistent base URL.** Dashboard and query calls both derive their path from one `ORCHESTRATOR_BASE_URL`, appended consistently — previously they defaulted this differently, which could silently break query submission once the env var was set.
- **No authentication.** Matches agent-service's current scope.