from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CandidateChunk(BaseModel):
    chunk_id: str
    text: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RerankRequest(BaseModel):
    query: str
    candidates: List[CandidateChunk]
    top_k: int = 5


class RerankedChunk(BaseModel):
    chunk_id: str
    text: str
    original_score: Optional[float]
    rerank_logit: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RerankResponse(BaseModel):
    query: str
    reranked: List[RerankedChunk]
    model: str
    latency_ms: float
    device: str