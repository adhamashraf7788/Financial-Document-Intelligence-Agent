import httpx

from .config import settings


class AgentClient:
    def __init__(self):
        self.base_url = settings.AGENT_URL
        self.timeout = settings.REQUEST_TIMEOUT

    async def query(
        self,
        question: str,
        document_id: str | None = None,
        api_key: str | None = None,
    ) -> dict:
        payload = {
            "question": question,
        }

        if document_id is not None:
            payload["document_id"] = document_id

        headers = {}

        if api_key:
            headers["X-API-Key"] = api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/agent/query",
                json=payload,
                headers=headers,
            )

        response.raise_for_status()

        return response.json()

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/health"
                )

            return response.status_code == 200

        except httpx.HTTPError:
            return False