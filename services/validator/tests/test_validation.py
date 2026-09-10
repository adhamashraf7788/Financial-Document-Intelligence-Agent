import pytest
from services.validator.validation import validate_answer, evaluate_formula
from fastapi.testclient import TestClient
from services.validator.main import app

def test_valid_direct_answer():
    payload = {
        "answer_type": "direct",
        "evidence": [{"document_id": "doc_017", "page": 1, "section": "Income Statement"}],
        "params": {"value": "$142.5M"},
    }
    result = validate_answer(payload)
    assert result.valid is True

def test_missing_evidence_rejected():
    payload = {
        "answer_type": "direct",
        "evidence": [],
        "params": {"value": "$142.5M"},
    }
    result = validate_answer(payload)
    assert result.valid is False
    assert "direct" in result.message

def test_unknown_answer_type_rejected():
    payload = {
        "answer_type": "comparison",
        "evidence": [],
        "params": {},
    }
    result = validate_answer(payload)
    assert result.valid is False
    assert "comparison" in result.message

def test_valid_calculated_answer():
    payload = {
        "answer_type": "calculated",
        "evidence": [
            {"document_id": "doc_041", "page": 2, "section": "Operating Expenses"},
            {"document_id": "doc_041", "page": 2, "section": "Operating Expenses"},
        ],
        "params": {"value": 13.636, "formula": "(3875-3410)/3410*100"},
    }
    result = validate_answer(payload)
    assert result.valid is True

def test_valid_multi_span_answer():
    payload = {
        "answer_type": "multi_span",
        "evidence": [{"document_id": "doc_022", "page": 3, "section": "Operating Expenses"}],
        "params": {"values": ["Marketing", "R&D", "Logistics"]},
    }
    result = validate_answer(payload)
    assert result.valid is True

def test_valid_insufficient_evidence_answer():
    payload = {
        "answer_type": "insufficient_evidence",
        "evidence": [],
        "params": {"reason": "No document in the indexed corpus reports restructuring expenses."},
    }
    result = validate_answer(payload)
    assert result.valid is True

def test_evaluate_formula_correct_math():
    assert evaluate_formula("(3875-3410)/3410*100") == pytest.approx(13.6363, rel=1e-3)


def test_evaluate_formula_rejects_code_injection():
    with pytest.raises(ValueError):
        evaluate_formula("__import__('os').system('echo hacked')")


def test_evaluate_formula_rejects_semicolon():
    with pytest.raises(ValueError):
        evaluate_formula("1+1; 2+2")

def test_multi_span_single_value_rejected():
    payload = {
        "answer_type": "multi_span",
        "evidence": [{"document_id": "doc_022", "page": 3}],
        "params": {"values": ["Marketing"]},
    }
    result = validate_answer(payload)
    assert result.valid is False


def test_calculated_missing_formula_rejected():
    payload = {
        "answer_type": "calculated",
        "evidence": [{"document_id": "doc_041", "page": 2}],
        "params": {"value": 13.4},
    }
    result = validate_answer(payload)
    assert result.valid is False

client = TestClient(app)


def test_endpoint_valid_direct_answer():
    payload = {
        "answer_type": "direct",
        "evidence": [{"document_id": "doc_017", "page": 1, "section": "Income Statement"}],
        "params": {"value": "$142.5M"},
    }
    response = client.post("/validate_answer", json=payload)
    assert response.status_code == 200
    assert response.json()["valid"] is True

def test_endpoint_invalid_answer_rejected():
    payload = {
        "answer_type": "direct",
        "evidence": [],
        "params": {"value": "$142.5M"},
    }
    response = client.post("/validate_answer", json=payload)
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_endpoint_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "answer-validator-api"}