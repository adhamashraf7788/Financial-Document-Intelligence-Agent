# Agent & UI Service API Contracts

## 1. Agent Service (`agent-service`)
- **Endpoint**: `POST /api/v1/agent/query`
- **Description**: Receives user question and optional document filters, processes via LangGraph, and returns schema-compliant grounded response.

### Request Body:
```json
{
  "question": "What was the operating income reported in 2020?",
  "document_id": "doc_017"
}
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