from fastapi import FastAPI, Header, HTTPException

from .config import settings
from .models import (
    DashboardResponse,
    DashboardStats,
    IndexedDocument,
    QueryRequest,
    RecentQuery,
    StructuredAgentOutput,
)
from .orchestrator import orchestrator


app = FastAPI(
    title="Orchestrator Service",
    version="1.0.0",
)


@app.get("/health")
async def health():
    agent_healthy = await orchestrator.agent_health()

    return {
        "status": "ok" if agent_healthy else "degraded",
        "service": "orchestrator-service",
        "checks": {
            "agent_service": agent_healthy,
        },
    }


@app.post(
    "/api/v1/query",
    response_model=StructuredAgentOutput,
)
async def query(
    request: QueryRequest,
    x_api_key: str | None = Header(default=None),
):
    if settings.ORCHESTRATOR_API_KEY:
        if x_api_key != settings.ORCHESTRATOR_API_KEY:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
            )

    try:
        return await orchestrator.query(
            request=request,
            api_key=x_api_key,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Orchestrator query failed: {str(exc)}",
        )


@app.get(
    "/api/v1/dashboard",
    response_model=DashboardResponse,
)
async def dashboard(
    x_api_key: str | None = Header(default=None),
):
    if settings.ORCHESTRATOR_API_KEY:
        if x_api_key != settings.ORCHESTRATOR_API_KEY:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
            )

    average_latency = orchestrator.get_average_latency()

    return DashboardResponse(
        dashboard_stats=DashboardStats(
            indexed_documents=0,
            total_tables=0,
            avg_latency_ms=average_latency,
        ),
        indexed_documents=[],
        recent_queries=[],
    )