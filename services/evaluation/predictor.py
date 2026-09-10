import os
import httpx
from shared.schemas import Answer, InsufficientEvidenceAnswer, Evidence, ANSWER_TYPE_MAP
from langfuse import observe

AGENT_SERVICE_URL = os.getenv(
    "AGENT_SERVICE_URL", "http://localhost:8000/api/v1/agent/query"
)

REQUEST_TIMEOUT = float(os.getenv("AGENT_REQUEST_TIMEOUT", "30.0"))


@observe()
def predict_answer(question: str, document_id: str | None = None) -> tuple[Answer, list[dict] | None]:
    payload = {"question": question}
    if document_id:
        payload["document_id"] = document_id

    try:
        response = httpx.post(AGENT_SERVICE_URL, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        answer_type = data.get("answer_type")
        answer_model = ANSWER_TYPE_MAP.get(answer_type)
        if answer_model is None:
            raise ValueError(f"Unknown answer_type from agent-service: {answer_type!r}")

        answer = answer_model.model_validate(data)

        retrieval_results = [
            {"metadata": {"document_id": ev.document_id}}
            for ev in answer.evidence
        ] if answer.evidence else None

        return answer, retrieval_results

    except Exception as exc:
        fallback = InsufficientEvidenceAnswer(
            answer_type="insufficient_evidence",
            evidence=[],
            params={"reason": f"agent-service call failed: {exc}"},
        )
        return fallback, None
