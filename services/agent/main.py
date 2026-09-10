import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException

from config import RETRIEVAL_SERVICE_URL, llm
from schemas import QueryRequest, StructuredAgentOutput
from graph.builder import agent_graph
from tools import get_http_client, close_http_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_service.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_http_client()  # warm the shared client (issue #7)
    yield
    await close_http_client()


app = FastAPI(title="LEDGER Financial Agent Service", version="3.0", lifespan=lifespan)


@app.post("/api/v1/agent/query", response_model=StructuredAgentOutput)
async def run_agent(request: QueryRequest):
    try:
        initial_state = {
            "question": request.question,
            "document_id": request.document_id,
            "retrieved_data": [],
            "final_output": None,
            "retry_count": 0,
        }
        result = await agent_graph.ainvoke(initial_state)
        return result["final_output"]
    except Exception as e:
        logger.exception("Unhandled error in run_agent")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Reports overall status plus each dependency's reachability
    (issue #6: previously returned a static 'ok' regardless of deps)."""
    checks = {"llm_configured": llm is not None}

    try:
        resp = await httpx.AsyncClient(timeout=3.0).get(
            RETRIEVAL_SERVICE_URL.rsplit("/api/", 1)[0] + "/health"
        )
        checks["retrieval_service"] = resp.status_code < 500
    except Exception as e:
        checks["retrieval_service"] = False
        checks["retrieval_service_error"] = str(e)

    overall = "ok" if checks["llm_configured"] and checks.get("retrieval_service") else "degraded"
    return {"status": overall, "service": "agent-service", "checks": checks}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)