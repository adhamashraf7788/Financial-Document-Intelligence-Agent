### retrieval-api (Chunking)

 *** Description ***: Receives structured output from doc-processor-api and runs section-aware and table-aware chunking rules to generate parent/child text chunks and Markdown table chunks.


 *** Request Example ***

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

 *** Response Example ***

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




### retrieval-api (Agent Query)

 *** Description ***: Executes hybrid retrieval (dense vectors + sparse BM25 keyword search), merges candidate pools, applies reranking, and returns top-K scored chunks to the agent-service

 *** Request Example ***
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "top_k": 30,
  "rerank_to": 5,
  "filters": {
    "document_id": null,
    "content_type": null
  }
}

 *** Response Example ***
{
  "query": "What was CTS's finished-goods balance in 2019?",
  "candidates_retrieved": 30,
  "top_k_returned": 5,
  "results": [
    {
      "chunk_id": "doc_041_p2_tbl_4d3823",
      "document_id": "doc_041",
      "page": 2,
      "section": "Balance Sheet",
      "content_type": "table",
      "text": "Section: Balance Sheet\n| Inventory Category | 2018 ($k) | 2019 ($k) |\n| --- | --- | --- |\n| Raw materials | 4,120 | 5,230 |\n| Work in progress | 1,850 | 2,100 |\n| Finished goods | 8,100 | 9,447 |",
      "score": 0.945,
      "retrieval_method": "hybrid+rerank",
      "metadata": {
        "is_complete_table": true,
        "num_rows": 3
      }
    },
    {
      "chunk_id": "doc_041_p2_child_9687f1",
      "document_id": "doc_041",
      "page": 2,
      "section": "Balance Sheet",
      "content_type": "text",
      "text": "Section: Balance Sheet\nFinished goods inventory increased due to higher manufacturing throughput during Q4.",
      "score": 0.812,
      "retrieval_method": "dense+rerank",
      "metadata": {
        "is_parent": false,
        "parent_id": "doc_041_p2_parent_77a1d8"
      }
    },
    {
      "chunk_id": "doc_041_p2_parent_77a1d8",
      "document_id": "doc_041",
      "page": 2,
      "section": "Balance Sheet",
      "content_type": "text",
      "text": "Section: Balance Sheet\nFinished goods inventory increased due to higher manufacturing throughput during Q4.",
      "score": 0.735,
      "retrieval_method": "bm25+rerank",
      "metadata": {
        "is_parent": true
      }
    },
    {
      "chunk_id": "doc_017_p1_tbl_b4aaa4",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "table",
      "text": "Section: Income Statement\n| Item | 2019 | 2020 |\n| --- | --- | --- |\n| Revenue | 1,200 | 1,450 |\n| Operating Expense | 900 | 1,050 |\n| Net Income | 300 | 400 |",
      "score": 0.518,
      "retrieval_method": "hybrid+rerank",
      "metadata": {
        "is_complete_table": true,
        "num_rows": 3
      }
    },
    {
      "chunk_id": "doc_017_p1_child_60dfdd",
      "document_id": "doc_017",
      "page": 1,
      "section": "Income Statement",
      "content_type": "text",
      "text": "Section: Income Statement\nTotal operating income for fiscal year 2020 was $142.5M compared to $120.0M in fiscal year 2019.",
      "score": 0.394,
      "retrieval_method": "dense+rerank",
      "metadata": {
        "is_parent": false,
        "parent_id": "doc_017_p1_parent_c3baa8"
      }
    }
  ]
}