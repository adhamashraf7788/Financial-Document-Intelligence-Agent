from typing import List, Dict, Any, Optional, Literal, Union
from pydantic import BaseModel, Field

class Block(BaseModel):
    block_id: str
    content_type: str  # "text" or "table"
    text: Optional[str] = None
    table_data: Optional[List[List[Any]]] = None
    bounding_box: Optional[List[float]] = None
    section: Optional[str] = "General"

class Page(BaseModel):
    page_number: int
    blocks: List[Block]

class DocumentProcessorResponse(BaseModel):
    document_id: str
    pages: List[Page]
    status: str

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    page: int
    section: str
    content_type: str  # "text" or "table"
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Evidence(BaseModel):
    document_id: str
    page: int
    section: str = ""

class DirectAnswer(BaseModel):
    answer_type: Literal["direct"] = "direct"
    evidence: List[Evidence] = Field(..., min_length=1)

    class Params(BaseModel):
        value: Union[str, float, int]

    params: Params

class CalculatedAnswer(BaseModel):
    answer_type: Literal["calculated"] = "calculated"
    evidence: List[Evidence] = Field(..., min_length=1)

    class Params(BaseModel):
        value: float
        formula: str

    params: Params

class MultiSpanAnswer(BaseModel):
    answer_type: Literal["multi_span"] = "multi_span"
    evidence: List[Evidence] = Field(..., min_length=1)

    class Params(BaseModel):
        values: List[Union[str, float, int]] = Field(..., min_length=2)

    params: Params

class InsufficientEvidenceAnswer(BaseModel):
    answer_type: Literal["insufficient_evidence"] = "insufficient_evidence"
    evidence: List[Evidence] = Field(default_factory=list)

    class Params(BaseModel):
        reason: str

    params: Params

Answer = Union[
    DirectAnswer,
    CalculatedAnswer,
    MultiSpanAnswer,
    InsufficientEvidenceAnswer,
]

ANSWER_TYPE_MAP = {
    "direct": DirectAnswer,
    "calculated": CalculatedAnswer,
    "multi_span": MultiSpanAnswer,
    "insufficient_evidence": InsufficientEvidenceAnswer,
}
