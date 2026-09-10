import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from config import MAX_QUERY_ATTEMPTS, RAW_PDFS_DIR
from schemas import QueryRequest, IngestRequest, IngestResponse, DashboardResponse, AnswerPayload
import clients
import query_log
import document_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    clients.get_http_client()
    yield
    await clients.close_http_client()


app = FastAPI(title="LEDGER Orchestrator Service", version="1.0", lifespan=lifespan)


# --- Query flow: agent-service -> answer-validator-api, retry once on rejection ---

@app.post("/api/v1/query", response_model=AnswerPayload)
async def run_query(request: QueryRequest):
    start = time.perf_counter()
    answer = None
    reject_message = None
    status = "FAILED"

    for attempt in range(MAX_QUERY_ATTEMPTS):
        answer, agent_error = await clients.ask_agent(request.question, request.document_id)

        if answer is None:
            elapsed_ms = (time.perf_counter() - start) * 1000
            query_log.record(request.question, elapsed_ms, "FAILED")
            raise HTTPException(status_code=502, detail=f"agent-service call failed: {agent_error}")

        valid, message, validator_error = await clients.validate_answer(answer)

        if validator_error is not None:
            elapsed_ms = (time.perf_counter() - start) * 1000
            query_log.record(request.question, elapsed_ms, "FAILED")
            raise HTTPException(status_code=502, detail=f"answer-validator-api call failed: {validator_error}")

        if valid:
            status = "VALIDATED"
            break

        reject_message = message
        status = "REJECTED"
        logger.warning("Query attempt %d rejected by validator: %s", attempt + 1, message)
        # loop again for the retry (same question, no hint — see README)

    elapsed_ms = (time.perf_counter() - start) * 1000
    query_log.record(request.question, elapsed_ms, status)

    if status == "REJECTED":
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {
                "reason": f"Answer failed validation after {MAX_QUERY_ATTEMPTS} attempt(s): {reject_message}"
            },
        }

    return answer


# --- Ingestion: manual, path-based, no upload/DB (see README) ---

@app.post("/api/v1/documents", response_model=IngestResponse)
async def ingest_document(request: IngestRequest):
    if not request.file_path.startswith(RAW_PDFS_DIR):
        raise HTTPException(
            status_code=400,
            detail=f"file_path must be under the shared mount {RAW_PDFS_DIR}",
        )
    if not os.path.isfile(request.file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    doc_data, doc_error = await clients.process_document(request.document_id, request.file_path)
    if doc_data is None:
        return IngestResponse(
            document_id=request.document_id,
            status="failed",
            stage_failed="doc_processing",
            detail=doc_error,
        )

    chunk_data, chunk_error = await clients.index_document(request.document_id, doc_data.get("pages", []))
    if chunk_data is None:
        return IngestResponse(
            document_id=request.document_id,
            status="failed",
            stage_failed="chunking",
            detail=chunk_error,
        )

    pages = doc_data.get("pages", [])
    table_count = sum(
        1 for p in pages for b in p.get("blocks", []) if b.get("content_type") == "table"
    )
    document_registry.register(
        document_id=request.document_id,
        filename=os.path.basename(request.file_path),
        pages=len(pages),
        tables=table_count,
    )

    return IngestResponse(
        document_id=request.document_id,
        status="success",
        pages=len(pages),
        tables=table_count,
    )


# --- Dashboard: real query log, real (if any) indexed docs ---

@app.get("/api/v1/dashboard", response_model=DashboardResponse)
async def dashboard():
    docs = document_registry.all_documents()
    return DashboardResponse(
        dashboard_stats={
            "indexed_documents": len(docs),
            "total_tables": document_registry.total_tables(),
            "avg_latency_ms": query_log.average_latency_ms(),
        },
        indexed_documents=docs,
        recent_queries=query_log.recent(),
    )


# --- Health ---

@app.get("/health")
async def health():
    agent_status, agent_error = await clients.agent_health()
    reachable = agent_status is not None
    overall = "ok" if reachable and agent_status.get("status") == "ok" else "degraded"

    checks = {"agent_service_reachable": reachable}
    if agent_status is not None:
        checks["agent_service_health"] = agent_status
    else:
        checks["agent_service_error"] = agent_error

    return {"status": overall, "service": "orchestrator-service", "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)