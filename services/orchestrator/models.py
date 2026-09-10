from pydantic import BaseModel
from typing import Any


class QueryRequest(BaseModel):
    question: str
    document_id: str | None = None


class Evidence(BaseModel):
    document_id: str
    page: int
    section: str | None = None


class AnswerParams(BaseModel):
    value: str | int | float | None = None
    formula: str | None = None
    values: list[Any] | None = None
    reason: str | None = None


class StructuredAgentOutput(BaseModel):
    answer_type: str
    evidence: list[Evidence]
    params: AnswerParams


class DashboardStats(BaseModel):
    indexed_documents: int = 0
    total_tables: int = 0
    avg_latency_ms: float = 0


class IndexedDocument(BaseModel):
    document_id: str
    filename: str
    pages: int = 0
    tables: int = 0


class RecentQuery(BaseModel):
    query_id: str
    question: str
    latency_ms: str
    status: str


class DashboardResponse(BaseModel):
    dashboard_stats: DashboardStats
    indexed_documents: list[IndexedDocument]
    recent_queries: list[RecentQuery]