import os
import logging
from fastapi import Header, HTTPException

logger = logging.getLogger("agent_service.auth")

AGENT_API_KEY = os.getenv("AGENT_API_KEY")  # unset = auth disabled (dev mode)

if not AGENT_API_KEY:
    logger.warning(
        "AGENT_API_KEY is not set — /api/v1/agent/query is UNAUTHENTICATED. "
        "Set AGENT_API_KEY in production."
    )


async def require_api_key(x_api_key: str = Header(default=None)):
    """FastAPI dependency. No-ops if AGENT_API_KEY isn't configured (local/dev),
    otherwise requires a matching X-API-Key header."""
    if AGENT_API_KEY is None:
        return
    if x_api_key != AGENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
