from typing import List, Optional, Any, Dict
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    document_id: Optional[str] = None


class IngestRequest(BaseModel):
    document_id: str
    file_path: str  # must already exist under RAW_PDFS_DIR — no upload, no DB


class IngestResponse(BaseModel):
    document_id: str
    status: str  # "success" | "failed"
    stage_failed: Optional[str] = None  # "doc_processing" | "chunking" | None
    pages: Optional[int] = None
    tables: Optional[int] = None
    detail: Optional[str] = None


class RecentQuery(BaseModel):
    query_id: str
    question: str
    latency_ms: str
    status: str  # "VALIDATED" | "REJECTED" | "FAILED"


class IndexedDocument(BaseModel):
    document_id: str
    filename: str
    pages: int
    tables: int


class DashboardStats(BaseModel):
    indexed_documents: int
    total_tables: int
    avg_latency_ms: float


class DashboardResponse(BaseModel):
    dashboard_stats: DashboardStats
    indexed_documents: List[IndexedDocument]
    recent_queries: List[RecentQuery]


# Answer payload is passed through from agent-service largely as-is; kept loose
# here since agent-service's schemas.py already enforces the strict shape —
# orchestrator doesn't need to re-declare the discriminated union, just forward it.
AnswerPayload = Dict[str, Any]