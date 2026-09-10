import logging
from typing import Optional, Tuple

import httpx

from config import (
    AGENT_SERVICE_URL,
    DOC_PROCESSOR_URL,
    CHUNKER_SERVICE_URL,
    VALIDATOR_SERVICE_URL,
    QUERY_TIMEOUT,
    VALIDATOR_TIMEOUT,
    INGESTION_TIMEOUT,
    HEALTH_CHECK_TIMEOUT,
)

logger = logging.getLogger("orchestrator.clients")

_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


async def close_http_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# --- agent-service ---

async def ask_agent(question: str, document_id: Optional[str]) -> Tuple[Optional[dict], Optional[str]]:
    """Returns (answer, error). error is None on success (HTTP 200)."""
    payload = {"question": question}
    if document_id:
        payload["document_id"] = document_id
    try:
        resp = await get_http_client().post(
            f"{AGENT_SERVICE_URL}/api/v1/agent/query", json=payload, timeout=QUERY_TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"agent-service returned {resp.status_code}: {resp.text[:300]}"
    except httpx.TimeoutException:
        return None, f"agent-service timed out after {QUERY_TIMEOUT}s"
    except Exception as e:
        logger.warning("agent-service call failed: %s", e)
        return None, str(e)


async def agent_health() -> Tuple[Optional[dict], Optional[str]]:
    try:
        resp = await get_http_client().get(f"{AGENT_SERVICE_URL}/health", timeout=HEALTH_CHECK_TIMEOUT)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"status {resp.status_code}"
    except Exception as e:
        return None, str(e)


# --- answer-validator-api ---

async def validate_answer(answer: dict) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Returns (valid, message, error). error set only on a request-level failure
    (validator unreachable) — a normal reject is (False, message, None)."""
    try:
        resp = await get_http_client().post(
            f"{VALIDATOR_SERVICE_URL}/validate_answer", json=answer, timeout=VALIDATOR_TIMEOUT
        )
        if resp.status_code == 200:
            body = resp.json()
            return body.get("valid"), body.get("message"), None
        return None, None, f"validator returned {resp.status_code}: {resp.text[:300]}"
    except httpx.TimeoutException:
        return None, None, f"validator timed out after {VALIDATOR_TIMEOUT}s"
    except Exception as e:
        logger.warning("validator call failed: %s", e)
        return None, None, str(e)


# --- doc-processor-api ---

async def process_document(document_id: str, file_path: str) -> Tuple[Optional[dict], Optional[str]]:
    payload = {"document_id": document_id, "file_path": file_path, "source_split": "train"}
    try:
        resp = await get_http_client().post(
            f"{DOC_PROCESSOR_URL}/process", json=payload, timeout=INGESTION_TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") != "success":
                return None, "doc-processor-api reported status=failed"
            return data, None
        return None, f"doc-processor-api returned {resp.status_code}: {resp.text[:300]}"
    except httpx.TimeoutException:
        return None, f"doc-processor-api timed out after {INGESTION_TIMEOUT}s"
    except Exception as e:
        logger.warning("doc-processor-api call failed: %s", e)
        return None, str(e)


# --- chunker (retrieval-api's /index-document) ---

async def index_document(document_id: str, pages: list) -> Tuple[Optional[dict], Optional[str]]:
    payload = {"document_id": document_id, "pages": pages}
    try:
        resp = await get_http_client().post(
            f"{CHUNKER_SERVICE_URL}/index-document", json=payload, timeout=INGESTION_TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"chunker returned {resp.status_code}: {resp.text[:300]}"
    except httpx.TimeoutException:
        return None, f"chunker timed out after {INGESTION_TIMEOUT}s"
    except Exception as e:
        logger.warning("chunker call failed: %s", e)
        return None, str(e)
