from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator


class EvidenceItem(BaseModel):
    document_id: str
    page: int
    section: str


class QueryRequest(BaseModel):
    question: str
    document_id: Optional[str] = None


# --- Per-type params models (issue #4: enforce shape structurally, not just at runtime) ---

class DirectParams(BaseModel):
    value: Union[str, float, int]


class CalculatedParams(BaseModel):
    value: float
    formula: str


class MultiSpanParams(BaseModel):
    values: List[str] = Field(min_length=2)


class InsufficientEvidenceParams(BaseModel):
    reason: str


class DirectAnswer(BaseModel):
    answer_type: Literal["direct"]
    evidence: List[EvidenceItem] = Field(min_length=1)
    params: DirectParams


class CalculatedAnswer(BaseModel):
    answer_type: Literal["calculated"]
    evidence: List[EvidenceItem] = Field(min_length=1)
    params: CalculatedParams


class MultiSpanAnswer(BaseModel):
    answer_type: Literal["multi_span"]
    evidence: List[EvidenceItem] = Field(min_length=1)
    params: MultiSpanParams


class InsufficientEvidenceAnswer(BaseModel):
    answer_type: Literal["insufficient_evidence"]
    evidence: List[EvidenceItem] = Field(default_factory=list)
    params: InsufficientEvidenceParams


# Discriminated union — FastAPI/Pydantic now rejects a malformed shape at the
# response-model boundary instead of silently accepting Dict[str, Any].
StructuredAgentOutput = Union[
    DirectAnswer, CalculatedAnswer, MultiSpanAnswer, InsufficientEvidenceAnswer
]
