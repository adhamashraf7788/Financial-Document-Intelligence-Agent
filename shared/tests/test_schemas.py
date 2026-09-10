import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from pydantic import ValidationError
from schemas import DirectAnswer, CalculatedAnswer, MultiSpanAnswer, InsufficientEvidenceAnswer, Evidence


def test_direct_valid():
    a = DirectAnswer(
        evidence=[{"document_id": "doc_017", "page": 1, "section": "Income Statement"}],
        params={"value": "$142.5M"},
    )
    assert a.answer_type == "direct"

def test_direct_missing_evidence_rejected():
    with pytest.raises(ValidationError):
        DirectAnswer(evidence=[], params={"value": "$142.5M"})


def test_direct_missing_value_rejected():
    with pytest.raises(ValidationError):
        DirectAnswer(evidence=[{"document_id": "doc_017", "page": 1}], params={})


def test_calculated_valid():
    a = CalculatedAnswer(
        evidence=[
            {"document_id": "doc_041", "page": 2, "section": "Operating Expenses"},
            {"document_id": "doc_041", "page": 2, "section": "Operating Expenses"},
        ],
        params={"value": 13.4, "formula": "(3875-3410)/3410*100"},
    )
    assert a.params.formula == "(3875-3410)/3410*100"


def test_calculated_missing_formula_rejected():
    with pytest.raises(ValidationError):
        CalculatedAnswer(
            evidence=[{"document_id": "doc_041", "page": 2}],
            params={"value": 13.4},
        )


def test_calculated_missing_evidence_rejected():
    with pytest.raises(ValidationError):
        CalculatedAnswer(evidence=[], params={"value": 13.4, "formula": "1+1"})


def test_calculated_value_wrong_type_rejected():
    with pytest.raises(ValidationError):
        CalculatedAnswer(
            evidence=[{"document_id": "doc_041", "page": 2}],
            params={"value": "not-a-number", "formula": "1+1"},
        )

def test_multi_span_valid():
    a = MultiSpanAnswer(
        evidence=[{"document_id": "doc_022", "page": 3, "section": "Operating Expenses"}],
        params={"values": ["Marketing", "R&D", "Logistics"]},
    )
    assert len(a.params.values) == 3


def test_multi_span_single_value_rejected():
    with pytest.raises(ValidationError):
        MultiSpanAnswer(
            evidence=[{"document_id": "doc_022", "page": 3}],
            params={"values": ["Marketing"]},
        )


def test_multi_span_missing_evidence_rejected():
    with pytest.raises(ValidationError):
        MultiSpanAnswer(evidence=[], params={"values": ["A", "B"]})

def test_insufficient_evidence_valid_with_no_evidence():
    a = InsufficientEvidenceAnswer(
        params={"reason": "No document in the indexed corpus reports restructuring expenses."}
    )
    assert a.evidence == []


def test_insufficient_evidence_missing_reason_rejected():
    with pytest.raises(ValidationError):
        InsufficientEvidenceAnswer(params={})

def test_evidence_zero_page_rejected():
    with pytest.raises(ValidationError):
        Evidence(document_id="doc_017", page=0)


def test_evidence_empty_document_id_rejected():
    with pytest.raises(ValidationError):
        Evidence(document_id="", page=1)