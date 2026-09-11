# import logging
# from contextlib import asynccontextmanager

# import httpx
# from fastapi import FastAPI, HTTPException

# from config import RETRIEVAL_SERVICE_URL, llm
# from schemas import QueryRequest, StructuredAgentOutput
# from graph.builder import agent_graph
# from tools import get_http_client, close_http_client

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("agent_service.main")




# from fastapi.middleware.cors import CORSMiddleware






# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     get_http_client()  # warm the shared client (issue #7)
#     yield
#     await close_http_client()


# app = FastAPI(title="LEDGER Financial Agent Service", version="3.0", lifespan=lifespan)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Adjust for production security as needed
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# @app.post("/api/v1/agent/query", response_model=StructuredAgentOutput)
# async def query_retrieval_service(question: str, top_k: int = 5):
#     client = get_http_client()
#     payload = {
#         "query": question,
#         "alpha": 0.5,
#         "candidates_retrieved": 30,
#         "top_k_returned": top_k
#     }
    
#     response = await client.post(RETRIEVAL_SERVICE_URL, json=payload)
#     response.raise_for_status()
#     return response.json()


# async def run_agent(request: QueryRequest):
#     try:
#         initial_state = {
#             "question": request.question,
#             "document_id": request.document_id,
#             "retrieved_data": [],
#             "final_output": None,
#             "retry_count": 0,
#         }
#         result = await agent_graph.ainvoke(initial_state)
#         return result["final_output"]
#     except Exception as e:
#         logger.exception("Unhandled error in run_agent")
#         raise HTTPException(status_code=500, detail=str(e))








# @app.get("/health")
# async def health():
#     """Reports overall status plus each dependency's reachability
#     (issue #6: previously returned a static 'ok' regardless of deps)."""
#     checks = {"llm_configured": llm is not None}

#     try:
#         resp = await httpx.AsyncClient(timeout=3.0).get(
#             RETRIEVAL_SERVICE_URL.rsplit("/api/", 1)[0] + "/health"
#         )
#         checks["retrieval_service"] = resp.status_code < 500
#     except Exception as e:
#         checks["retrieval_service"] = False
#         checks["retrieval_service_error"] = str(e)

#     overall = "ok" if checks["llm_configured"] and checks.get("retrieval_service") else "degraded"
#     return {"status": overall, "service": "agent-service", "checks": checks}


# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(app, host="0.0.0.0", port=7000)





import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import RETRIEVAL_SERVICE_URL, llm
from schemas import QueryRequest, StructuredAgentOutput
from graph.builder import agent_graph
from tools import get_http_client, close_http_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_service.main")


# In-memory query history store (max 100 entries)
QUERY_HISTORY: List[Dict[str, Any]] = []
MAX_HISTORY_SIZE = 100


def add_to_history(entry: Dict[str, Any]):
    """Add entry to query history, maintaining max size."""
    QUERY_HISTORY.insert(0, entry)
    if len(QUERY_HISTORY) > MAX_HISTORY_SIZE:
        QUERY_HISTORY.pop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_http_client()  # warm shared client
    yield
    await close_http_client()


app = FastAPI(title="LEDGER Financial Agent Service", version="3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/agent/query", response_model=StructuredAgentOutput)
async def run_agent(request: QueryRequest):
    """Executes the full LangGraph agent workflow to answer financial queries."""
    query_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()
    
    try:
        initial_state = {
            "question": request.question,
            "document_id": request.document_id,
            "retrieved_data": [],
            "final_output": None,
            "retry_count": 0,
        }
        result = await agent_graph.ainvoke(initial_state)
        final_output = result["final_output"]
        
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        retry_count = result.get("retry_count", 0)
        retrieved_data = result.get("retrieved_data", [])
        
        # Extract chunk details for dashboard
        chunk_details = []
        for idx, chunk in enumerate(retrieved_data):
            metadata = chunk.get("metadata", {})
            chunk_details.append({
                "chunk_id": chunk.get("chunk_id"),
                "rank": idx + 1,
                "score": chunk.get("score"),
                "rerank_logit": chunk.get("rerank_logit"),
                "document_id": metadata.get("document_id"),
                "page": metadata.get("page"),
                "section": metadata.get("section"),
                "content_type": metadata.get("content_type"),
            })
        
        # Record query history
        history_entry = {
            "query_id": query_id,
            "question": request.question,
            "document_id": request.document_id,
            "latency_ms": latency_ms,
            "retry_count": retry_count,
            "answer_type": final_output.get("answer_type") if final_output else "error",
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "chunk_details": chunk_details,
        }
        add_to_history(history_entry)
        
        return final_output
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        history_entry = {
            "query_id": query_id,
            "question": request.question,
            "document_id": request.document_id,
            "latency_ms": latency_ms,
            "retry_count": 0,
            "answer_type": "error",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "chunk_details": [],
        }
        add_to_history(history_entry)
        logger.exception("Unhandled error in run_agent")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/agent/direct-search")
async def direct_search(request: QueryRequest, top_k: int = 5):
    """Bypasses agent reasoning and directly queries the retrieval service."""
    client = get_http_client()
    payload = {
        "query": request.question,
        "alpha": 0.5,
        "candidates_retrieved": 30,
        "top_k_returned": top_k
    }
    
    response = await client.post(RETRIEVAL_SERVICE_URL, json=payload)
    response.raise_for_status()
    return response.json()


@app.get("/health")
async def health():
    checks = {"llm_configured": llm is not None}

    try:
        base_retrieval_url = RETRIEVAL_SERVICE_URL.split("/search")[0]
        resp = await httpx.AsyncClient(timeout=3.0).get(f"{base_retrieval_url}/documents/all?limit=1")
        checks["retrieval_service"] = resp.status_code < 500
    except Exception as e:
        checks["retrieval_service"] = False
        checks["retrieval_service_error"] = str(e)

    overall = "ok" if checks["llm_configured"] and checks.get("retrieval_service") else "degraded"
    return {"status": overall, "service": "agent-service", "checks": checks}


@app.get("/api/v1/dashboard")
async def dashboard():
    """Returns dashboard stats, document list, structured values, and recent query history."""
    # Fetch all chunks from retrieval service
    all_chunks = []
    try:
        base_retrieval_url = RETRIEVAL_SERVICE_URL.split("/search")[0]
        resp = await httpx.AsyncClient(timeout=10.0).get(f"{base_retrieval_url}/documents/all?limit=5000")
        if resp.status_code == 200:
            all_chunks = resp.json().get("results", [])
    except Exception as e:
        logger.warning(f"Failed to fetch document chunks: {e}")
    
    # Aggregate by document
    doc_map = {}
    for chunk in all_chunks:
        meta = chunk.get("metadata", {})
        doc_id = meta.get("document_id", "unknown")
        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "document_id": doc_id,
                "filename": meta.get("filename", doc_id),
                "pages": set(),
                "tables": 0,
                "sections": set(),
                "content_types": set(),
                "sample_values": [],
                "chunk_count": 0,
            }
        d = doc_map[doc_id]
        d["chunk_count"] += 1
        if meta.get("page"):
            d["pages"].add(meta.get("page"))
        if meta.get("content_type") == "table":
            d["tables"] += 1
        if meta.get("section"):
            d["sections"].add(meta.get("section"))
        if meta.get("content_type"):
            d["content_types"].add(meta.get("content_type"))
        
        # Extract structured values from chunk text
        text = chunk.get("text", "")
        if text:
            vals = extract_structured_values(text)
            d["sample_values"].extend(vals)
    
    # Build document list
    document_list = []
    total_tables = 0
    for doc_id, d in doc_map.items():
        # Deduplicate sample values
        unique_values = list(dict.fromkeys(d["sample_values"]))[:10]
        total_tables += d["tables"]
        document_list.append({
            "document_id": doc_id,
            "filename": d["filename"],
            "pages": sorted(list(d["pages"])),
            "page_count": len(d["pages"]),
            "tables": d["tables"],
            "sections": sorted(list(d["sections"]))[:10],
            "content_types": list(d["content_types"]),
            "sample_values": unique_values,
            "chunk_count": d["chunk_count"],
        })
    
    # Calculate stats
    indexed_docs = len(document_list)
    avg_latency = 0
    recent_successful = [q for q in QUERY_HISTORY if q.get("status") == "success"][:20]
    if recent_successful:
        avg_latency = round(sum(q["latency_ms"] for q in recent_successful) / len(recent_successful), 2)
    
    # Pipeline health metrics
    pipeline_health = compute_pipeline_health()
    
    recent_queries = QUERY_HISTORY[:20]
    
    return {
        "dashboard_stats": {
            "indexed_documents": indexed_docs,
            "total_tables": total_tables,
            "avg_latency_ms": avg_latency,
        },
        "indexed_documents": document_list,
        "pipeline_health": pipeline_health,
        "recent_queries": recent_queries,
    }


def extract_structured_values(text: str) -> list[str]:
    """Extract financial structured values from text."""
    import re
    values = []
    
    # Currency amounts: $1.2B, $1,200,000, $1.2 million, etc.
    currency_pattern = r'\$[\d,]+\.?\d*\s*(?:million|billion|thousand|M|B|K)?'
    for match in re.finditer(currency_pattern, text, re.IGNORECASE):
        val = match.group().strip()
        if len(val) > 2:
            values.append(val)
    
    # Percentages: 15.5%, 15%
    pct_pattern = r'\d+\.?\d*\s*%'
    for match in re.finditer(pct_pattern, text):
        values.append(match.group().strip())
    
    # Financial keywords with nearby numbers
    financial_keywords = [
        'revenue', 'income', 'profit', 'loss', 'earnings', 'ebitda',
        'assets', 'liabilities', 'equity', 'cash', 'debt',
        'operating income', 'net income', 'gross profit', 'margin',
        'total assets', 'total liabilities', 'shareholders equity'
    ]
    text_lower = text.lower()
    for keyword in financial_keywords:
        if keyword in text_lower:
            # Find numbers near this keyword
            idx = text_lower.find(keyword)
            context = text[max(0, idx-50):idx+len(keyword)+50]
            # Extract numbers from context
            nums = re.findall(r'[\$\d,]+\.?\d*\s*(?:million|billion|thousand|M|B|K|%)?', context)
            for n in nums:
                n = n.strip()
                if n and len(n) > 1:
                    values.append(f"{keyword}: {n}")
    
    return values[:20]  # Limit per chunk


def compute_pipeline_health() -> dict:
    """Compute pipeline health metrics from query history."""
    if not QUERY_HISTORY:
        return {
            "retrieval_avg_candidates": 0,
            "retrieval_avg_rerank_ms": 0,
            "agent_avg_llm_calls": 0,
            "validator_pass_rate": 0,
            "total_queries": 0,
            "success_rate": 0,
        }
    
    recent = QUERY_HISTORY[:50]
    total = len(recent)
    successful = [q for q in recent if q.get("status") == "success"]
    success_count = len(successful)
    
    # Average chunk details metrics
    total_chunks = 0
    total_rerank = 0.0
    rerank_count = 0
    
    for q in recent:
        chunks = q.get("chunk_details", [])
        total_chunks += len(chunks)
        for c in chunks:
            if c.get("rerank_logit") is not None:
                total_rerank += abs(c["rerank_logit"])
                rerank_count += 1
    
    avg_candidates = round(total_chunks / total, 1) if total > 0 else 0
    avg_rerank = round((total_rerank / rerank_count) * 1000, 1) if rerank_count > 0 else 0
    
    # Estimate LLM calls (1 per query + retries)
    avg_llm = round(sum(q.get("retry_count", 0) + 1 for q in recent) / total, 1) if total > 0 else 0
    
    return {
        "retrieval_avg_candidates": avg_candidates,
        "retrieval_avg_rerank_ms": avg_rerank,
        "agent_avg_llm_calls": avg_llm,
        "validator_pass_rate": round(success_count / total, 2) if total > 0 else 0,
        "total_queries": total,
        "success_rate": round(success_count / total, 2) if total > 0 else 0,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7000)