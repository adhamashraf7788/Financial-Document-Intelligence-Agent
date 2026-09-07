# Document Processing Service

## Endpoint

`POST /process`

The Document Processing service receives the path of a financial-report PDF and returns structured pages containing text and table blocks.

## Request

```json
{
  "document_id": "doc_017",
  "file_path": "/data/raw_pdfs/doc_017.pdf",
  "source_split": "train"
}
```

### Request fields

| Field          | Type   | Required | Description                                                        |
| -------------- | ------ | -------- | ------------------------------------------------------------------ |
| `document_id`  | string | Yes      | Unique identifier of the document                                  |
| `file_path`    | string | Yes      | Path to the PDF file accessible by the Document Processing service |
| `source_split` | string | Yes      | Dataset split. Allowed values: `train`, `validation`, `test`       |

## Response

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
          "text": "Total operating income for fiscal year 2020 was...",
          "table_data": null,
          "bounding_box": [100, 200, 500, 240],
          "section": "Income Statement"
        },
        {
          "block_id": "doc_017_p1_t01",
          "content_type": "table",
          "text": null,
          "table_data": [
            ["Item", "2019", "2020"],
            ["Revenue", "1,200", "1,450"]
          ],
          "bounding_box": [100, 250, 700, 500],
          "section": "Income Statement"
        }
      ]
    }
  ],
  "status": "success"
}
```

## Response fields

### `DocumentResponse`

| Field         | Type   | Description                              |
| ------------- | ------ | ---------------------------------------- |
| `document_id` | string | ID of the processed document             |
| `pages`       | array  | List of processed PDF pages              |
| `status`      | string | Processing result: `success` or `failed` |

### `Page`

| Field         | Type    | Description                                |
| ------------- | ------- | ------------------------------------------ |
| `page_number` | integer | PDF page number                            |
| `blocks`      | array   | Text and table blocks detected on the page |

### `Block`

| Field          | Type        | Description                                         |
| -------------- | ----------- | --------------------------------------------------- |
| `block_id`     | string      | Unique identifier for the block                     |
| `content_type` | string      | Either `text` or `table`                            |
| `text`         | string/null | Extracted text for a text block                     |
| `table_data`   | array/null  | Extracted table data for a table block              |
| `bounding_box` | array       | `[x0, y0, x1, y1]` coordinates of the block         |
| `section`      | string/null | Detected document section associated with the block |

## Failed Response

When the PDF cannot be found or processing fails, the service returns:

```json
{
  "document_id": "doc_017",
  "pages": [],
  "status": "failed"
}
```

## Processing Flow

```text
POST /process
      ↓
Validate PDF path
      ↓
Open PDF with PyMuPDF
      ↓
Render page
      ↓
PP-StructureV3
      ↓
Extract page OCR + table structure/OCR
      ↓
Table reconstruction / cleaning
      ↓
Section detection
      ↓
Create text/table blocks
      ↓
DocumentResponse
```

The service creates text blocks from PP-StructureV3 OCR matched to detected layout regions and table blocks from the table structure and table-specific OCR results. Each block includes its bounding box and associated document section.

---

# retrieval-api (Chunking)

Description: Receives structured output from doc-processor-api and runs section-aware and table-aware chunking rules to generate parent/child text chunks and Markdown table chunks.

### Endpoint

`POST /index-document`

or

`POST /test-chunking` for a dry run that returns chunks without indexing.

### Request Body

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

### Response

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
      "metadata": {
        "is_parent": true
      }
    },
    {
      "chunk_id": "doc_017_p1_child_60dfdd",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "text",
      "text": "Section: Income Statement\nTotal operating income for fiscal year 2020 was $142.5M compared to $120.0M in fiscal year 2019.",
      "metadata": {
        "is_parent": false,
        "parent_id": "doc_017_p1_parent_c3baa8"
      }
    },
    {
      "chunk_id": "doc_017_p1_tbl_b4aaa4",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "table",
      "text": "Section: Income Statement\n| Item | 2019 | 2020 |\n| --- | --- | --- |\n| Revenue | 1,200 | 1,450 |\n| Operating Expense | 900 | 1,050 |\n| Net Income | 300 | 400 |",
      "metadata": {
        "is_complete_table": true,
        "num_rows": 3
      }
    }
  ]
}
```

> Note: this is chunker output only — no `score` here, since nothing has been retrieved/ranked yet. Downstream indexing (`/index-document`) embeds these chunks and stores them in Weaviate.

---

# retrieval-api (Agent Query)

Description: Executes hybrid retrieval (dense vectors + sparse BM25 keyword search) and returns the top-K scored chunks to the agent-service. Does not itself rerank — the standalone reranker-service is the only cross-encoder reranking step in the pipeline.

### Endpoint

`POST /search/hybrid`

> Important — this is a query-parameter endpoint, not a JSON body. The route is defined with plain FastAPI function args (`query: str`, `alpha: float = Query(...)`, etc.), not a Pydantic request model. Send these as URL query params (`params=` in httpx/requests), not as a JSON payload.

Sibling endpoints with the same parameter shape:

* `POST /search/bm25` (no `alpha`)
* `POST /search/vector` (no `alpha`)

### Request Parameters

| Param                  | Type  | Default  | Notes                                       |
| ---------------------- | ----- | -------- | ------------------------------------------- |
| `query`                | str   | required | The search query                            |
| `alpha`                | float | `0.5`    | `0.0` = pure BM25, `1.0` = pure vector      |
| `candidates_retrieved` | int   | `30`     | How many candidates to fetch before slicing |
| `top_k_returned`       | int   | `5`      | How many to actually return in the response |

### Example Call

```text
POST /search/hybrid?query=What+was+CTS%27s+finished-goods+balance+in+2019%3F&alpha=0.5&candidates_retrieved=30&top_k_returned=20
```

### Response

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

---

# Strict Answer Schema

## Base Structure

```json
{
  "answer_type": "<type_name>",
  "evidence": [
    {
      "document_id": "...",
      "page": 0,
      "section": "..."
    }
  ],
  "params": {}
}
```

## Type: `direct`

Required params: `value` (string or number).

Required: at least 1 evidence citation.

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
    "value": "$142.5M"
  }
}
```

## Type: `calculated`

Required params: `value` (number), `formula` (string).

Required: one evidence citation per operand used in the formula.

```json
{
  "answer_type": "calculated",
  "evidence": [
    {
      "document_id": "doc_041",
      "page": 2,
      "section": "Operating Expenses"
    },
    {
      "document_id": "doc_041",
      "page": 2,
      "section": "Operating Expenses"
    }
  ],
  "params": {
    "value": 13.4,
    "formula": "(3875-3410)/3410*100"
  }
}
```

## Type: `multi_span`

Required params: `values` (array, 2+ items).

Required: at least one evidence citation per value (one citation may cover multiple values if they come from the same cell/passage).

```json
{
  "answer_type": "multi_span",
  "evidence": [
    {
      "document_id": "doc_022",
      "page": 3,
      "section": "Operating Expenses"
    }
  ],
  "params": {
    "values": [
      "Marketing",
      "R&D",
      "Logistics"
    ]
  }
}
```

## Type: `insufficient_evidence`

Required params: `reason` (string).

Evidence array is optional and may be empty.

```json
{
  "answer_type": "insufficient_evidence",
  "evidence": [],
  "params": {
    "reason": "No document in the indexed corpus reports restructuring expenses."
  }
}
```

Fixtures: one example JSON per type lives in `mock-data/answers/` (`direct.json`, `calculated.json`, `multi_span.json`, `insufficient_evidence.json`) — use these to build your stub before the real agent-service is ready.

---

# reranker-service (Cross-Encoder Reranking)

Description: Stateless service that takes a query + a candidate pool (from retrieval-api) and returns the top-K candidates reordered by cross-encoder relevance. This is the only reranking step in the pipeline.

### Endpoint

`POST /rerank`

This endpoint accepts a JSON body. Unlike retrieval-api's search endpoints, this one is a Pydantic request model.

### Request Body

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

`candidates` may be an empty array (`[]`) — valid input, e.g. when retrieval-api found nothing. Only `chunk_id`, `text`, `score`, and `metadata` are read; any other top-level field on a candidate is silently ignored, so anything that needs to survive (citations, provenance) must be inside `metadata`.

### Response

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

`rerank_logit` is a **raw cross-encoder logit** — no sigmoid applied. It is not a 0–1 probability; treat it as a relative ranking score only. On an empty `candidates` input, `reranked` is `[]`.

---

# End-to-End Call Sequence (Agent Side)

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

# each item:
# chunk_id, text, original_score, rerank_logit, metadata
```
