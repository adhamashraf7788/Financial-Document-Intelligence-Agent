import pytest

from services.orchestrator.clients import AgentClient


class MockResponse:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "answer_type": "direct",
            "evidence": [],
            "params": {
                "value": "100"
            },
        }


class MockAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, *args, **kwargs):
        return MockResponse()

    async def get(self, *args, **kwargs):
        return MockResponse()


@pytest.mark.asyncio
async def test_agent_query(monkeypatch):
    monkeypatch.setattr(
        "services.orchestrator.clients.httpx.AsyncClient",
        MockAsyncClient,
    )

    client = AgentClient()

    result = await client.query(
        question="What is the revenue?",
        document_id="doc_017",
        api_key="test-key",
    )

    assert result["answer_type"] == "direct"
    assert result["params"]["value"] == "100"


@pytest.mark.asyncio
async def test_agent_health(monkeypatch):
    monkeypatch.setattr(
        "services.orchestrator.clients.httpx.AsyncClient",
        MockAsyncClient,
    )

    client = AgentClient()

    result = await client.health()

    assert result is True