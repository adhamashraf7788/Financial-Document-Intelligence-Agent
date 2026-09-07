## retrieval-api (Chunking)

Description : Receives structured output from doc-processor-api and runs section-aware and table-aware chunking rules to generate parent/child text chunks and Markdown table chunks.

Endpoint: `POST /index-document` (or `/test-chunking` for a dry run that returns chunks without indexing)

Request Body (JSON)
```json
{
  "document_id": "doc_017",
  "pages": [
    {
      "page_number": 1,
      "blocks": [
        {
          "block_id": "doc_017_p1_b01",
          "content_type": "text",
          "text": "Total operating income for fiscal year 2020 was $142.5M compared to $120.0M in fiscal year 2019.",
          "table_data": null,
          "bounding_box": [10, 20, 100, 50],
          "section": "Income Statement"
        }
      ]
    }
  ]
}
```

Response (JSON)
```json
{
  "document_id": "doc_017",
  "total_chunks_created": 3,
  "chunks": [
    {
      "chunk_id": "doc_017_p1_parent_c3baa8",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "text",
      "text": "Section: Income Statement\nTotal operating income for fiscal year 2020 was $142.5M compared to $120.0M in fiscal year 2019.",
      "metadata": { "is_parent": true }
    },
    {
      "chunk_id": "doc_017_p1_child_60dfdd",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "text",
      "text": "Section: Income Statement\nTotal operating income for fiscal year 2020 was $142.5M compared to $120.0M in fiscal year 2019.",
      "metadata": { "is_parent": false, "parent_id": "doc_017_p1_parent_c3baa8" }
    },
    {
      "chunk_id": "doc_017_p1_tbl_b4aaa4",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "table",
      "text": "Section: Income Statement\n| Item | 2019 | 2020 |\n| --- | --- | --- |\n| Revenue | 1,200 | 1,450 |\n| Operating Expense | 900 | 1,050 |\n| Net Income | 300 | 400 |",
      "metadata": { "is_complete_table": true, "num_rows": 3 }
    }
  ]
}
```

> Note: this is chunker output only — no `score` here, since nothing has been retrieved/ranked yet. Downstream indexing (`/index-document`) embeds these chunks and stores them in Weaviate.

---

## retrieval-api (Agent Query)

Description: Executes hybrid retrieval (dense vectors + sparse BM25 keyword search) and returns the top-K scored chunks to the agent-service. Does not itself rerank — the standalone reranker-service is the only cross-encoder reranking step in the pipeline.

Endpoint: `POST /search/pipeline`

> Important — this is a query-parameter endpoint, not a JSON body.The route is defined with plain FastAPI function args (`query: str`, `alpha: float = Query(...)`, etc.), not a Pydantic request model. Send these as URL query params (`params=` in httpx/requests), not as a JSON payload.

Sibling endpoints with the same param shape: `POST /search/bm25` (no `alpha`), `POST /search/vector` (no `alpha`).

Request (query params)

| Param | Type | Default | Notes |
|---|---|---|---|
| `query` | str | required | the search query |
| `alpha` | float | `0.5` | `0.0` = pure BM25, `1.0` = pure vector |
| `candidates_retrieved` | int | `30` | how many candidates to fetch before slicing |
| `top_k_returned` | int | `5` | how many to actually return in the response |

Example call:
```
POST /search/pipeline?query=What+was+CTS%27s+finished-goods+balance+in+2019%3F&alpha=0.5&candidates_retrieved=30&top_k_returned=20
```

Response (JSON)
```json
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "search_mode": "hybrid",
  "alpha": 0.5,
  "candidates_retrieved": 30,
  "top_k_returned": 5,
  "results": [
    {
      "chunk_id": "doc_041_p2_tbl_4d3823",
      "text": "Section: Balance Sheet\n| Inventory Category | 2018 ($k) | 2019 ($k) |\n| --- | --- | --- |\n| Raw materials | 4,120 | 5,230 |\n| Work in progress | 1,850 | 2,100 |\n| Finished goods | 8,100 | 9,447 |",
      "score": 0.945,
      "metadata": {
        "document_id": "doc_041",
        "page": 2,
        "section": "Balance Sheet",
        "content_type": "table",
        "retrieval_method": "hybrid",
        "is_complete_table": true,
        "num_rows": 3
      }
    },
    {
      "chunk_id": "doc_041_p2_child_9687f1",
      "text": "Section: Balance Sheet\nFinished goods inventory increased due to higher manufacturing throughput during Q4.",
      "score": 0.812,
      "metadata": {
        "document_id": "doc_041",
        "page": 2,
        "section": "Balance Sheet",
        "content_type": "text",
        "retrieval_method": "dense",
        "is_parent": false,
        "parent_id": "doc_041_p2_parent_77a1d8"
      }
    },
    {
      "chunk_id": "doc_041_p2_parent_77a1d8",
      "text": "Section: Balance Sheet\nFinished goods inventory increased due to higher manufacturing throughput during Q4.",
      "score": 0.735,
      "metadata": {
        "document_id": "doc_041",
        "page": 2,
        "section": "Balance Sheet",
        "content_type": "text",
        "retrieval_method": "bm25",
        "is_parent": true
      }
    },
    {
      "chunk_id": "doc_017_p1_tbl_b4aaa4",
      "text": "Section: Income Statement\n| Item | 2019 | 2020 |\n| --- | --- | --- |\n| Revenue | 1,200 | 1,450 |\n| Operating Expense | 900 | 1,050 |\n| Net Income | 300 | 400 |",
      "score": 0.518,
      "metadata": {
        "document_id": "doc_017",
        "page": 1,
        "section": "Income Statement",
        "content_type": "table",
        "retrieval_method": "hybrid",
        "is_complete_table": true,
        "num_rows": 3
      }
    },
    {
      "chunk_id": "doc_017_p1_child_60dfdd",
      "text": "Section: Income Statement\nTotal operating income for fiscal year 2020 was $142.5M compared to $120.0M in fiscal year 2019.",
      "score": 0.394,
      "metadata": {
        "document_id": "doc_017",
        "page": 1,
        "section": "Income Statement",
        "content_type": "text",
        "retrieval_method": "dense",
        "is_parent": false,
        "parent_id": "doc_017_p1_parent_c3baa8"
      }
    }
  ]
}
```

## Strict Answer Schema:

 ### Base Structure:

{
  "answer_type": "<type_name>",
  "evidence": [ { "document_id": "...", "page": 0, "section": "..." } ],
  "params": { ... }
}

 ### Type: direct
Required params: value (string or number). Required: at least 1 evidence citation.
{
  "answer_type": "direct",
  "evidence": [ { "document_id": "doc_017", "page": 1, "section": "Income Statement" } ],
  "params": { "value": "$142.5M" }
}

 ### Type: calculated
Required params: value (number), formula (string). Required: one evidence citation per operand used in the formula.
{
  "answer_type": "calculated",
  "evidence": [
    { "document_id": "doc_041", "page": 2, "section": "Operating Expenses" },
    { "document_id": "doc_041", "page": 2, "section": "Operating Expenses" }
  ],
  "params": { "value": 13.4, "formula": "(3875-3410)/3410*100" }
}

 ### Type: multi_span
Required params: values (array, 2+ items). Required: at least one evidence citation per value (one citation may cover multiple values if they come from the same cell/passage).
{
  "answer_type": "multi_span",
  "evidence": [
    { "document_id": "doc_022", "page": 3, "section": "Operating Expenses" }
  ],
  "params": { "values": ["Marketing", "R&D", "Logistics"] }
}

 ### Type: insufficient_evidence
Required params: reason (string). Evidence array is optional and may be empty.
{
  "answer_type": "insufficient_evidence",
  "evidence": [],
  "params": { "reason": "No document in the indexed corpus reports restructuring expenses." }
}

 Fixtures: One example JSON per type lives in mock-data/answers/ (direct.json, calculated.json, multi_span.json, insufficient_evidence.json) — use these to build your stub before the real agent-service is ready.


## reranker-service (Cross-Encoder Reranking)

Description: Stateless service that takes a query + a candidate pool (from retrieval-api) and returns the top-K candidates reordered by cross-encoder relevance. This is the only reranking step in the pipeline.

Endpoint: `POST /rerank` (JSON body — this one IS a Pydantic model, unlike retrieval-api's search endpoints)

Request (JSON body)
```json
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "candidates": [
    {
      "chunk_id": "doc_041_p2_tbl_4d3823",
      "text": "Section: Balance Sheet\n| Inventory Category | 2018 ($k) | 2019 ($k) |...",
      "score": 0.945,
      "metadata": {
        "document_id": "doc_041",
        "page": 2,
        "section": "Balance Sheet",
        "content_type": "table",
        "retrieval_method": "hybrid",
        "is_complete_table": true,
        "num_rows": 3
      }
    }
  ],
  "top_k": 5
}
```
`candidates` may be an empty array (`[]`) — valid input, e.g. when retrieval-api found nothing. Only `chunk_id`, `text`, `score`, `metadata` are read; any other top-level field on a candidate is silently ignored, so anything that needs to survive (citations, provenance) must be inside `metadata`.

Response (JSON)
```json
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "reranked": [
    {
      "chunk_id": "doc_041_p2_tbl_4d3823",
      "text": "Section: Balance Sheet\n| Inventory Category | 2018 ($k) | 2019 ($k) |...",
      "original_score": 0.945,
      "rerank_logit": 4.2,
      "metadata": {
        "document_id": "doc_041",
        "page": 2,
        "section": "Balance Sheet",
        "content_type": "table",
        "retrieval_method": "hybrid",
        "is_complete_table": true,
        "num_rows": 3
      }
    }
  ],
  "model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
  "latency_ms": 45.2,
  "device": "cuda"
}
```
`rerank_logit` is a **raw cross-encoder logit** — no sigmoid applied. Not a 0-1 probability; treat it as a relative ranking score only. On an empty `candidates` input, `reranked` is `[]`.

---

## End-to-End Call Sequence (Agent Side)

```python
# 1. Hybrid search (retrieval-api) — query params, NOT a JSON body
retrieval_resp = await http.post(
    "http://retrieval:8000/search/hybrid",
    params={
        "query": query,
        "alpha": 0.5,
        "candidates_retrieved": 30,
        "top_k_returned": 20
    }
)

# 2. Rerank (reranker-service) — JSON body
rerank_resp = await http.post(
    "http://reranker:8000/rerank",
    json={
        "query": query,
        "candidates": retrieval_resp.json()["results"],
        "top_k": 5
    }
)

final_chunks = rerank_resp.json()["reranked"]
# each item: chunk_id, text, original_score, rerank_logit, metadata
```
