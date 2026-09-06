# Reranker Service

## Branch Context

- **Branch**: `feature/reranker`
- **Iteration**: 1 — Foundation & Core Components
- **Depends on**: Retrieval service (provides candidate chunks)

## What This Service Does

Cross-encoder reranking for financial document retrieval. Takes a query + candidate chunks from the retrieval service → returns top-K reranked with raw logits.

## Architecture

```
Agent/Orchestrator
       │
       ├──────────────────┐
       ▼                  ▼
┌──────────────────┐ ┌──────────────────┐
│ Retrieval Svc    │ │ Reranker Svc     │
│ Internal: 8000   │ │ Internal: 8000   │
│ Host: 8000       │ │ Host: 8001       │
│ /search/hybrid   │ │ /rerank          │
└──────────────────┘ └──────────────────┘
       │                  ▲
       │ candidates       │ reranked (logits)
       └──────────────────┘
```

> **Note on ports:** Every service listens on port `8000` *inside* its own container — that's normal and never conflicts, since each container has its own isolated network namespace. Conflicts only happen at the **host** level, when mapping container ports out to your machine. So locally, retrieval-api is mapped to host port `8000` and reranker to host port `8001` — but container-to-container calls (e.g. agent → reranker) always use the internal port `8000` via Compose's DNS (`http://reranker:8000`), regardless of what host port is used for local curl/testing.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/rerank` | Rerank candidates with cross-encoder |
| GET    | `/health` | Service + model status |

### POST /rerank

**Request**
```json
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "candidates": [
    {
      "chunk_id": "doc_041_p2_tbl_4d3823",
      "text": "Section: Balance Sheet\n| Inventory Category | 2018 ($k) | 2019 ($k) |\n| --- | --- | --- |\n| Raw materials | 4,120 | 5,230 |\n| Work in progress | 1,850 | 2,100 |\n| Finished goods | 8,100 | 9,447 |",
      "score": 0.945,
      "metadata": {"is_complete_table": true, "num_rows": 3}
    }
  ],
  "top_k": 5
}
```

**Response**
```json
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "reranked": [
    {
      "chunk_id": "doc_041_p2_tbl_4d3823",
      "text": "Section: Balance Sheet\n| Inventory Category | 2018 ($k) | 2019 ($k) |...",
      "original_score": 0.945,
      "rerank_logit": 4.2,
      "metadata": {"is_complete_table": true, "num_rows": 3}
    }
  ],
  "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
  "latency_ms": 45.2,
  "device": "cuda"
}
```

**Note:** `candidates` may be empty (`[]`) — this is a valid input (e.g. when upstream retrieval found nothing). In that case `/rerank` returns `"reranked": []` rather than erroring, so the agent can safely route to an `insufficient_evidence` answer.

## Model

- **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (22M params)
- **Output**: Raw logits (no sigmoid applied)
- **Device**: Auto-detect CUDA, FP16 inference on GPU
- **Batch size**: 32 (unified CPU/GPU)
- **Max length**: 512 tokens

## Optimizations

- **FP16** on GPU (`.half()`) — ~2x memory reduction
- **Warmup** on startup — eliminates cold-start latency
- **Batch inference** — 32 pairs per forward pass
- **No `torch.compile`** — overhead exceeds gain for a 22M param model; variable input shapes cause recompilation

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | HuggingFace model ID |
| `RERANKER_BATCH_SIZE` | `32` | Inference batch size |

## Local Development

### Build (CPU/GPU auto-detect)
```bash
docker build -f services/reranker/Dockerfile -t reranker .
```

### Run with GPU
```bash
docker run --gpus all -p 8001:8000 reranker
```

### Run on CPU
```bash
docker run -p 8001:8000 reranker
```

> Host port `8001` is used consistently for both GPU and CPU runs, mapped to the container's internal port `8000`. This avoids colliding with retrieval-api, which is mapped to host port `8000`.

### Test
```bash
curl http://localhost:8001/health

curl -X POST http://localhost:8001/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "revenue 2020",
    "candidates": [
      {"chunk_id": "1", "text": "Revenue was $100M in 2020", "score": 0.8}
    ],
    "top_k": 5
  }'
```

## Integration with Retrieval

Agent calls sequentially. Note these use **internal** container ports (`8000` for both services) since this code runs inside the Docker Compose network, not on your host machine:

```python
# 1. Hybrid search (retrieval service)
candidates = await http.post("http://retrieval:8000/search/hybrid", {
    "query": query, "alpha": 0.5, "candidates_retrieved": 30, "top_k_returned": 20
})

# 2. Rerank (reranker service)
final = await http.post("http://reranker:8000/rerank", {
    "query": query,
    "candidates": candidates["results"],
    "top_k": 5
})
# final["reranked"][i].rerank_logit = raw logit
```

## Candidate Shape Contract

Retrieval-api's `results` array must return each candidate as:
```json
{
  "chunk_id": "...",
  "text": "...",
  "score": 0.0,
  "metadata": {
    "document_id": "...",
    "page": 0,
    "section": "...",
    "content_type": "...",
    "retrieval_method": "hybrid | dense | bm25"
  }
}
```
Only `chunk_id`, `text`, `score`, and `metadata` are read by the reranker's `CandidateChunk` model — any other top-level fields are silently ignored by Pydantic, so anything retrieval-api needs preserved downstream (citations, provenance, etc.) **must** live inside `metadata`, not at the top level.

## Mock Test Data

Use `mock-data/retrieval_results/q1.json` for local testing — contains realistic candidates matching the shape above.

## No Database Dependency

This service is stateless. No vector DB, no persistence. Model downloads from HuggingFace on first container start (~50MB).