# eval-service (Evaluation & Observability Service)

Runs the TAT-DQA benchmark end-to-end against a predictor, scores the
results (Exact Match, F1, numerical accuracy, retrieval Recall@K /
Precision@K / MRR where available, correct-refusal rate on unanswerable
questions), and traces every step in Langfuse.
Runs the TAT-DQA benchmark end-to-end against the financial agent pipeline, scores the results across answer quality (Exact Match, F1, Numerical Accuracy, correct-refusal rate on unanswerable questions) and retrieval quality (Recall@K, Precision@K, MRR), runs pipeline variant experiments, and traces every step in Langfuse.

## Endpoints

```
### 1. Full Benchmark Run
```http
POST /evaluate
Content-Type: application/json
Body (optional): { "questions_path": "mock-data/eval_questions/questions_setA_practice.json" }

{
  "questions_path": "mock-data/eval_questions/questions_setA_practice.json"
}
```
*`questions_path` is optional; defaults to the practice question set if omitted. Returns the aggregated benchmark report.*

Defaults to the practice question set if no body is given. Returns the
aggregated benchmark report.
### 2. Pipeline Variant Experiment Comparison
```http
POST /evaluate/experiment
Content-Type: application/json

{
  "experiment_name": "reranker_ablation",
  "questions_path": "mock-data/eval_questions/questions_setA_practice.json",
  "sample_size": 20
}
```
*Compares baseline vs. variant pipeline performance, calculates absolute differences and percentage changes across quality and latency metrics, and outputs an automated conclusion on whether the change measurably helped or hurt.*

### 3. Health & Readiness Checks
```http
GET /health
Response: { "status": "ok", "service": "eval-service" }
```
```http
GET /ping
Response: { "status": "ok" }
```
Basic health check.

## Current predictor: a stub, not the real agent
---

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
## Predictor & Agent Integration

**To wire this up for real:** swap `predict_answer()` to call
agent-service's `/api/v1/agent/query` endpoint instead of generating a
random answer, and pass the real retrieval results (from whatever
service/step surfaces them) into `score_retrieval()` in
`harness.py`'s `score_question()`.
`predictor.py`'s `predict_answer()` connects the evaluation harness directly to the live agent pipeline:
- Sends a POST request to `agent-service` (`http://localhost:8000/api/v1/agent/query`, configurable via `AGENT_SERVICE_URL` and `AGENT_REQUEST_TIMEOUT`).
- Validates the response against `ANSWER_TYPE_MAP` from `shared/schemas.py`.
- **Retrieval Metric Extraction:** Parses the returned `evidence` citations into document ID candidates and passes them directly to `score_retrieval()`. This enables calculation of real `recall_at_k`, `precision_at_k`, and `mrr` against gold evidence.
- **Resilient Fallback:** If `agent-service` is unreachable or times out, it catches the exception and returns a graceful `(InsufficientEvidenceAnswer, None)` tuple so the benchmark suite finishes without hanging.

---

## Pipeline Experiments

Implemented in `services/evaluation/experiments.py` to satisfy the project experiment requirement:
> *"Langfuse datasets/experiments should be used to compare pipeline variants (e.g. chunking strategy, reranker on/off) and justify design choices with measured results, not intuition."*

- **Metric Delta Calculation (`compute_metric_deltas`):** Calculates `diff`, `pct_change`, and an `improved` flag for:
  - Answer Quality: `exact_match`, `f1`, `numerical_accuracy`, `correct_refusal_rate`
  - Retrieval Quality: `recall_at_k`, `precision_at_k`, `mrr`
  - System Performance: `avg_latency_ms_per_question` (lower is improved)
- **Automated Conclusions (`generate_experiment_conclusion`):** Evaluates trade-offs and generates human-readable verdicts (e.g., *"Variant improved performance across 4 metric(s) (with 0 regression(s)). Measurable positive impact."*).
- **Langfuse Experiment Tracing:** Wrapped in `@observe()` to generate linked traces in Langfuse for each experiment run.

---

## Tracing

Every step (`run_benchmark`, `load_questions`, `predict_answer`,
`score_question`) is wrapped in Langfuse's `@observe()`, so a single
`/evaluate` call produces one parent trace with ~200+ nested child steps
for a 100-question run — visible in the Langfuse dashboard under
Tracing, filterable by step name.
Every step (`run_benchmark`, `load_questions`, `predict_answer`, `score_question`, `run_pipeline_experiment`) is wrapped in Langfuse's `@observe()`. A single evaluation run creates a root trace with nested child spans for each question, visible and filterable in the Langfuse dashboard.

---

## Running it

**Directly:**
```bash
cd services/evaluation
pip install -r requirements.txt
cd ../..
# from the project root
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

---

## Testing

```bash
python -m pytest services/evaluation/tests/ -v
services\evaluation\venv\Scripts\python -m pytest services/evaluation/tests/ -v
```

Covers: EM/F1/numerical-accuracy scoring, retrieval Recall@K/Precision@K/MRR
(against hand-built fixture data, not live retrieval), and the harness's
overall report shape.

## For orchestrator-api / integration

- `POST http://<eval-host>:8000/evaluate` — run the full benchmark, get
  back a report.
- No other service currently depends on eval-service directly; this is a
  standalone diagnostic/grading tool, not part of the live answer path.
Covers:
- `test_harness.py`: Benchmark report shape, valid metric ranges, and offline mock safety.
- `test_scorer.py`: Exact Match, token F1, Numerical Accuracy with scale parsing (thousands, millions, percent, negative parentheses), and Retrieval metrics (`Recall@K`, `Precision@K`, `MRR`).
- `test_experiments.py`: Metric delta math, automated conclusions, offline mock pipeline experiment execution, and API endpoint verification.
