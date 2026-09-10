import pytest
from fastapi.testclient import TestClient

from services.orchestrator.models import QueryRequest
from services.orchestrator.orchestrator import Orchestrator
from services.orchestrator.main import app
from services.orchestrator.orchestrator import orchestrator


@pytest.mark.asyncio
async def test_query_returns_structured_output(monkeypatch):
    orchestrator = Orchestrator()

    async def mock_query(
        question: str,
        document_id: str | None = None,
        api_key: str | None = None,
    ):
        return {
            "answer_type": "direct",
            "evidence": [
                {
                    "document_id": "doc_017",
                    "page": 1,
                    "section": "Income Statement",
                }
            ],
            "params": {
                "value": "100",
            },
        }

    monkeypatch.setattr(
        orchestrator.agent_client,
        "query",
        mock_query,
    )

    request = QueryRequest(
        question="What is the revenue?",
        document_id="doc_017",
    )

    result = await orchestrator.query(request)

    assert result.answer_type == "direct"
    assert result.params.value == "100"
    assert len(result.evidence) == 1


@pytest.mark.asyncio
async def test_average_latency_starts_at_zero():
    orchestrator = Orchestrator()

    assert orchestrator.get_average_latency() == 0.0


def test_query_endpoint(monkeypatch):
    async def mock_query(
        request,
        api_key=None,
    ):
        return {
            "answer_type": "direct",
            "evidence": [
                {
                    "document_id": "doc_017",
                    "page": 1,
                    "section": "Income Statement",
                }
            ],
            "params": {
                "value": "100",
            },
        }

    monkeypatch.setattr(
        orchestrator,
        "query",
        mock_query,
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/query",
        json={
            "question": "What is the revenue?",
            "document_id": "doc_017",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer_type"] == "direct"
    assert data["params"]["value"] == "100"
    assert len(data["evidence"]) == 1
    
def test_query_endpoint_rejects_missing_question():
    client = TestClient(app)

    response = client.post(
        "/api/v1/query",
        json={
            "document_id": "doc_017",
        },
    )

    assert response.status_code == 422