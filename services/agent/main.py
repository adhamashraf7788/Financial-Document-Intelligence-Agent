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
    """Returns dashboard stats and recent query history with chunk details."""
    # Fetch document stats from retrieval service
    doc_stats = {"indexed_documents": 0, "total_tables": 0}
    try:
        base_retrieval_url = RETRIEVAL_SERVICE_URL.split("/search")[0]
        resp = await httpx.AsyncClient(timeout=5.0).get(f"{base_retrieval_url}/documents/all?limit=1000")
        if resp.status_code == 200:
            all_chunks = resp.json().get("results", [])
            doc_ids = set()
            table_count = 0
            for chunk in all_chunks:
                metadata = chunk.get("metadata", {})
                doc_ids.add(metadata.get("document_id"))
                if metadata.get("content_type") == "table":
                    table_count += 1
            doc_stats = {
                "indexed_documents": len(doc_ids),
                "total_tables": table_count,
            }
    except Exception as e:
        logger.warning(f"Failed to fetch document stats: {e}")
    
    # Calculate average latency from recent successful queries
    recent_successful = [q for q in QUERY_HISTORY if q.get("status") == "success"][:20]
    avg_latency = 0
    if recent_successful:
        avg_latency = round(sum(q["latency_ms"] for q in recent_successful) / len(recent_successful), 2)
    
    # Return last 20 queries for the recent queries table
    recent_queries = QUERY_HISTORY[:20]
    
    return {
        "dashboard_stats": {
            "indexed_documents": doc_stats["indexed_documents"],
            "total_tables": doc_stats["total_tables"],
            "avg_latency_ms": avg_latency,
        },
        "indexed_documents": [],  # Could be expanded with document list
        "recent_queries": recent_queries,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7000)