from typing import Literal, Union
from pydantic import BaseModel


class Evidence(BaseModel):
    document_id: str
    page: int
    section: str | None = None


class DirectAnswer(BaseModel):
    answer_type: Literal["direct"]
    evidence: list[Evidence]
    params: dict


class CalculatedAnswer(BaseModel):
    answer_type: Literal["calculated"]
    evidence: list[Evidence]
    params: dict


class MultiSpanAnswer(BaseModel):
    answer_type: Literal["multi_span"]
    evidence: list[Evidence]
    params: dict


class InsufficientEvidenceAnswer(BaseModel):
    answer_type: Literal["insufficient_evidence"]
    evidence: list[Evidence] = []
    params: dict


Answer = Union[DirectAnswer, CalculatedAnswer, MultiSpanAnswer, InsufficientEvidenceAnswer]