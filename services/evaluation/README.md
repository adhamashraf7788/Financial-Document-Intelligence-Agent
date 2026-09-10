# eval-service (Evaluation & Observability Service)

Runs the TAT-DQA benchmark end-to-end against a predictor, scores the
results (Exact Match, F1, numerical accuracy, retrieval Recall@K /
Precision@K / MRR where available, correct-refusal rate on unanswerable
questions), and traces every step in Langfuse.

## Endpoint

```
POST /evaluate
Content-Type: application/json
Body (optional): { "questions_path": "mock-data/eval_questions/questions_setA_practice.json" }
```

Defaults to the practice question set if no body is given. Returns the
aggregated benchmark report.

```
GET /ping
```
Basic health check.

## Current predictor: a stub, not the real agent

`predictor.py`'s `predict_answer()` currently returns a random,
schema-valid answer for every question — it does not call agent-service,
retrieval-api, or any LLM. This means:
- `exact_match` / `f1` / `numerical_accuracy` will always be near 0 — that's
  expected and not a bug in the scoring itself.
- `recall_at_k` / `precision_at_k` / `mrr` are always `null` in the report,
  since `score_retrieval()` is deliberately called with
  `retrieval_results=None` everywhere until this service is wired to a
  real per-question retrieval call.
- `system_performance.llm_calls_per_query`, `avg_token_usage`, and
  `approximate_cost_usd` stay at `0`/`null` for the same reason — there's
  no real LLM in the loop yet to measure.

**To wire this up for real:** swap `predict_answer()` to call
agent-service's `/api/v1/agent/query` endpoint instead of generating a
random answer, and pass the real retrieval results (from whatever
service/step surfaces them) into `score_retrieval()` in
`harness.py`'s `score_question()`.

## Tracing

Every step (`run_benchmark`, `load_questions`, `predict_answer`,
`score_question`) is wrapped in Langfuse's `@observe()`, so a single
`/evaluate` call produces one parent trace with ~200+ nested child steps
for a 100-question run — visible in the Langfuse dashboard under
Tracing, filterable by step name.

## Running it

**Directly:**
```bash
cd services/evaluation
pip install -r requirements.txt
cd ../..
uvicorn services.evaluation.main:app --port 8001
```
(Run `uvicorn` from the project root, not from inside
`services/evaluation/` — its imports are package-relative.)

**In Docker:**
```bash
# from the project root
docker build -t eval-service -f services/evaluation/Dockerfile .
docker run --env-file services/evaluation/.env -p 8001:8000 eval-service
```

## Testing

```bash
python -m pytest services/evaluation/tests/ -v
```

Covers: EM/F1/numerical-accuracy scoring, retrieval Recall@K/Precision@K/MRR
(against hand-built fixture data, not live retrieval), and the harness's
overall report shape.

## For orchestrator-api / integration

- `POST http://<eval-host>:8000/evaluate` — run the full benchmark, get
  back a report.
- No other service currently depends on eval-service directly; this is a
  standalone diagnostic/grading tool, not part of the live answer path.
