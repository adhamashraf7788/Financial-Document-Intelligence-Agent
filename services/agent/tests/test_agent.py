from fastapi.testclient import TestClient
from main import app, calculate
client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_calculate_tool():
    res = calculate.invoke("3875 - 3410")
    assert res["success"] is True
    assert res["value"] == 465.0

def test_agent_query_endpoint():
    response = client.post("/api/v1/agent/query", json={"question": "What is the net income?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer_type" in data
    assert data["answer_type"] in ["direct", "calculated", "multi_span", "insufficient_evidence"]