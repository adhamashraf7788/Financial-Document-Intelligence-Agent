import time

from .clients import AgentClient
from .models import (
    QueryRequest,
    StructuredAgentOutput,
)


class Orchestrator:
    def __init__(self):
        self.agent_client = AgentClient()

        self.total_queries = 0
        self.total_latency_ms = 0.0

    async def query(
        self,
        request: QueryRequest,
        api_key: str | None = None,
    ) -> StructuredAgentOutput:

        start_time = time.perf_counter()

        result = await self.agent_client.query(
            question=request.question,
            document_id=request.document_id,
            api_key=api_key,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        self.total_queries += 1
        self.total_latency_ms += latency_ms

        return StructuredAgentOutput.model_validate(result)

    async def agent_health(self) -> bool:
        return await self.agent_client.health()

    def get_average_latency(self) -> float:
        if self.total_queries == 0:
            return 0.0

        return self.total_latency_ms / self.total_queries


orchestrator = Orchestrator()