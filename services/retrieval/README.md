# Agentic Hybrid Retrieval Pipeline

An agentic retrieval pipeline for financial document intelligence that combines **query planning, hybrid retrieval, deduplication, and cross-encoder reranking** to retrieve high-quality evidence from financial documents.

---

## Pipeline Execution Flow

### 1. Document Ingestion Flow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. Document Ingestion Flow                            │
└─────────────────────────────────────────────────────────────────────────────┘
  Parsed Doc ──► DocumentChunker ──► BGE-M3 Embedding ──► Weaviate Vector Store
                 (Text & Tables)    (BAAI/bge-m3)        (Schema & Metadata)
```

The ingestion pipeline:

1. Receives a parsed document.
2. Splits the document into searchable chunks containing text and tables.
3. Generates dense embeddings using **BGE-M3**.
4. Stores the chunks, embeddings, and associated metadata in **Weaviate**.

---

### 2. Agent Query Pipeline Flow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       2. Agent Query Pipeline Flow                          │
└─────────────────────────────────────────────────────────────────────────────┘
  User Query ──► Query Planning ──► Hybrid Search ──► Deduplication ──► Cross-Encoder
                 (Ollama LLM)       (Weaviate DB)     (Highest Score)  (ms-marco)
```

The query pipeline consists of four main stages:

### 1. Query Planning

The user's original query is analyzed by an LLM running locally through **Ollama** using `qwen2.5:1.5b`.

The query planner determines whether the question is simple or complex:

* **Simple queries** are rewritten into a more retrieval-friendly query.
* **Complex or multi-year queries** are decomposed into multiple sub-queries.

For example:

```text
Original Query:
"What was the operating income change from 2020 to 2021?"

Generated Queries:
1. "What was the operating income in 2020?"
2. "What was the operating income in 2021?"
```

---

### 2. Hybrid Search

Each generated query is independently searched against **Weaviate** using hybrid retrieval.

The retrieval combines:

* **Dense vector search** using BGE-M3 embeddings.
* **Sparse BM25 search** for keyword-based matching.

The `alpha` parameter controls the balance between the two retrieval methods:

```text
alpha = 0.0  → Pure BM25
alpha = 0.5  → Balanced hybrid search
alpha = 1.0  → Pure vector search
```

---

### 3. Deduplication

Results retrieved from multiple sub-queries are combined into a single candidate set.

Duplicate chunks are removed based on their `chunk_id`.

When the same chunk is retrieved by multiple sub-queries, the **highest retrieval score is retained**.

This prevents duplicate evidence from occupying multiple candidate positions.

---

### 4. Cross-Encoder Reranking

The deduplicated candidates are passed to a **cross-encoder reranker** based on `ms-marco`.

Unlike the initial retrieval stage, the cross-encoder evaluates the relationship between:

```text
Query ↔ Candidate Chunk
```

and produces a final **reranking logit score**.

The candidates are then sorted according to their reranking scores, and the highest-ranked results are returned.

---

# Installation & Setup

## Prerequisites

Make sure the following are installed and available:

* Python **3.10+**
* [Ollama](https://ollama.com/)
* Weaviate
* Required Python dependencies

---

## 1. Start Ollama

Install and start Ollama locally:

```bash
ollama serve
```

Then pull the required query-planning model:

```bash
ollama pull qwen2.5:1.5b
```

The query planner uses:

```text
qwen2.5:1.5b
```

---

## 2. Start Weaviate

The retrieval pipeline requires a running Weaviate instance.

The expected ports are:

```text
HTTP → 8085
gRPC → 50052
```

Make sure the Weaviate instance is running before starting the retrieval service.

---

# API Documentation

## Ingestion Endpoints

### `POST /index-document`

Chunks a parsed document, generates BGE-M3 embeddings, and stores the resulting objects in Weaviate.

#### Request Body

```text
DocumentProcessorResponse
```

The request body should contain the parsed document structure expected by the document processing pipeline.

#### Response

```json
{
  "document_id": "doc_12345",
  "total_chunks_indexed": 42
}
```

---

# Search Pipeline

## `POST /search/pipeline`

Executes the complete agentic retrieval pipeline.

The endpoint performs:

1. Query analysis and planning.
2. Query rewriting or sub-query decomposition.
3. Parallel hybrid searches against Weaviate.
4. Candidate deduplication.
5. Cross-encoder reranking.
6. Final top-k result selection.

### Endpoint

```text
POST /search/pipeline
```

### Parameter Style

The endpoint uses **URL query parameters**, which correspond to plain FastAPI function arguments.

---

## Request Parameters

| Parameter              | Type    | Default | Required | Description                                                                                |
| ---------------------- | ------- | ------: | :------: | ------------------------------------------------------------------------------------------ |
| `query`                | `str`   |       — |    Yes   | The user's original search question.                                                       |
| `alpha`                | `float` |   `0.5` |    No    | Hybrid search weight. `0.0` = pure BM25, `1.0` = pure vector search.                       |
| `candidates_retrieved` | `int`   |    `30` |    No    | Maximum number of candidate chunks retrieved per generated sub-query before deduplication. |
| `top_k_returned`       | `int`   |     `5` |    No    | Number of final reranked results to return.                                                |

---

# Example Request

```bash
curl -X POST "http://localhost:8000/search/pipeline?query=What%20was%20the%20operating%20income%20change%20from%202020%20to%202021%3F&alpha=0.5&candidates_retrieved=30&top_k_returned=3"
```

---

# Example Response

```json
{
  "query": "What was the operating income change from 2020 to 2021?",
  "search_mode": "hybrid",
  "alpha": 0.5,
  "is_complex": true,
  "generated_queries": [
    "What was the operating income in 2020?",
    "What was the operating income in 2021?"
  ],
  "candidates_retrieved": 18,
  "top_k_returned": 3,
  "results": [
    {
      "chunk_id": "doc_12_p3_child_a1b2c3",
      "text": "Section: Financial Highlights\nOperating income for 2021 was $120M compared to $95M in 2020...",
      "score": 0.8124,
      "rerank_logit": 4.512,
      "metadata": {
        "document_id": "doc_12",
        "page": 3,
        "section": "Financial Highlights",
        "content_type": "text",
        "retrieval_method": "hybrid"
      }
    },
    {
      "chunk_id": "doc_12_p5_tbl_d4e5f6",
      "text": "Section: Income Statement\n| Year | Operating Income |\n| --- | --- |\n| 2020 | $95M |\n| 2021 | $120M |",
      "score": 0.7651,
      "rerank_logit": 3.894,
      "metadata": {
        "document_id": "doc_12",
        "page": 5,
        "section": "Income Statement",
        "content_type": "table",
        "is_complete_table": true,
        "num_rows": 2,
        "retrieval_method": "hybrid"
      }
    },
    {
      "chunk_id": "doc_12_p4_child_g7h8i9",
      "text": "Section: Operations\nTotal revenue grew, driving operating margins up year-over-year...",
      "score": 0.6982,
      "rerank_logit": 1.205,
      "metadata": {
        "document_id": "doc_12",
        "page": 4,
        "section": "Operations",
        "content_type": "text",
        "is_parent": false,
        "parent_id": "doc_12_p4_parent_x1y2z3",
        "retrieval_method": "hybrid"
      }
    }
  ]
}
```

---

# Response Fields

| Field                  | Description                                                              |
| ---------------------- | ------------------------------------------------------------------------ |
| `query`                | The original user query.                                                 |
| `search_mode`          | Retrieval strategy used by the pipeline.                                 |
| `alpha`                | Dense/BM25 weighting used during hybrid search.                          |
| `is_complex`           | Indicates whether the query required decomposition.                      |
| `generated_queries`    | Queries generated by the query planner.                                  |
| `candidates_retrieved` | Number of unique candidates remaining after retrieval and deduplication. |
| `top_k_returned`       | Number of final results returned after reranking.                        |
| `results`              | Final ranked retrieval results.                                          |

### Result Object

Each result contains:

| Field          | Description                                                    |
| -------------- | -------------------------------------------------------------- |
| `chunk_id`     | Unique identifier of the retrieved chunk.                      |
| `text`         | Content of the retrieved chunk.                                |
| `score`        | Hybrid retrieval score.                                        |
| `rerank_logit` | Cross-encoder reranking score.                                 |
| `metadata`     | Document, page, section, content type, and retrieval metadata. |

---

# Architecture Summary

```text
                         ┌─────────────────────┐
                         │    Parsed Document  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Document Chunker   │
                         │   Text + Tables     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       BGE-M3        │
                         │     Embeddings      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      Weaviate       │
                         │ Vector + BM25 Index │
                         └──────────┬──────────┘
                                    │
                                    │
User Query ─────────────────────────┘
     │
     ▼
┌─────────────────────┐
│    Query Planning   │
│   Qwen 2.5 1.5B     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Query Rewrite /     │
│ Decomposition       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Hybrid Search    │
│ Dense + BM25        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Deduplication    │
│ Max Retrieval Score │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Cross-Encoder       │
│ Reranking (MS-MARCO)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     Top-K Results   │
└─────────────────────┘
```

---

## Technology Stack

| Component          | Technology             |
| ------------------ | ---------------------- |
| Query Planning     | Ollama + Qwen 2.5 1.5B |
| Embeddings         | BAAI/bge-m3            |
| Vector Database    | Weaviate               |
| Sparse Retrieval   | BM25                   |
| Dense Retrieval    | BGE-M3 Vector Search   |
| Retrieval Strategy | Hybrid Search          |
| Reranking          | MS-MARCO Cross-Encoder |
| API                | FastAPI                |
| Language           | Python 3.10+           |

---

## Retrieval Strategy

The pipeline follows a **retrieve → deduplicate → rerank** architecture:

```text
Query
  │
  ├──► Query Planning
  │       │
  │       ├──► Query 1 ──► Hybrid Search ──┐
  │       ├──► Query 2 ──► Hybrid Search ──┤
  │       └──► Query N ──► Hybrid Search ──┤
  │                                        │
  │                                        ▼
  │                               Deduplication
  │                                        │
  │                                        ▼
  │                               Cross-Encoder
  │                                 Reranking
  │                                        │
  │                                        ▼
  └──────────────────────────────────► Top-K
```

This architecture allows the system to handle both **simple retrieval questions** and **complex multi-part or multi-year financial questions**, while using reranking to improve the relevance of the final retrieved evidence.
