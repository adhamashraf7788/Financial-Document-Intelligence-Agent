import logging
from typing import Optional, Tuple

import httpx

from config import (
    ORCHESTRATOR_BASE_URL,
    ORCHESTRATOR_DASHBOARD_PATH,
    ORCHESTRATOR_QUERY_PATH,
    REQUEST_TIMEOUT_QUERY,
    REQUEST_TIMEOUT_DASHBOARD,
)

logger = logging.getLogger("ui_service.api_client")


async def fetch_health() -> Tuple[Optional[dict], Optional[str]]:
    """Returns (data, error). error is None on success.
    Hits agent-service's /health directly (not under /api/v1)."""
    url = f"{ORCHESTRATOR_BASE_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_DASHBOARD) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Health check returned {resp.status_code}"
    except Exception as e:
        logger.warning("Health check failed: %s", e)
        return None, str(e)


async def fetch_dashboard() -> Tuple[Optional[dict], Optional[str]]:
    """Returns (data, error). error is None on success."""
    url = f"{ORCHESTRATOR_BASE_URL}{ORCHESTRATOR_DASHBOARD_PATH}"
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_DASHBOARD) as client:
            resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Orchestrator returned {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        logger.warning("Dashboard fetch failed: %s", e)
        return None, str(e)


async def submit_query(question: str, document_id: Optional[str]) -> Tuple[Optional[dict], Optional[str]]:
    """Returns (data, error). error is None on success.
    Never substitutes mock data here (issue #1) — caller decides how to present a failure."""
    url = f"{ORCHESTRATOR_BASE_URL}{ORCHESTRATOR_QUERY_PATH}"
    payload = {"question": question}
    if document_id and document_id.strip():
        payload["document_id"] = document_id.strip()

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_QUERY) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"Orchestrator returned {resp.status_code}: {resp.text[:200]}"
    except httpx.TimeoutException:
        return None, f"Orchestrator request timed out after {REQUEST_TIMEOUT_QUERY}s."
    except Exception as e:
        logger.warning("Query submission failed: %s", e)
        return None, str(e)