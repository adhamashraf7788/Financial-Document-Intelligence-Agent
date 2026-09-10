import time
import torch
from typing import List
from sentence_transformers import CrossEncoder

from services.reranker.models import RerankRequest, RerankResponse, RerankedChunk


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 32,
        max_length: int = 512
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = CrossEncoder(
            model_name,
            max_length=max_length,
            device=self.device
        )

        if self.device == "cuda":
            self.model.model.half()

        self._warmup()

    def _warmup(self):
        dummy_pairs = [("warmup query", "warmup document text for initialization")] * self.batch_size
        _ = self.model.predict(
            dummy_pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_tensor=True
        )
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def rerank(self, request: RerankRequest) -> RerankResponse:
        start = time.perf_counter()
        if not request.candidates:
            return RerankResponse(
                query=request.query,
                reranked=[],
                model=self.model_name,
                latency_ms=(time.perf_counter() - start) * 1000,
                device=self.device
            )

        pairs = [(request.query, c.text if c.text.strip() else " ") for c in request.candidates]
        logits = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_tensor=True
        )

        logits_np = logits.cpu().numpy()

        scored = list(zip(request.candidates, logits_np))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:request.top_k]

        reranked = [
            RerankedChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                original_score=c.score,
                rerank_logit=float(logit),
                metadata=c.metadata
            )
            for c, logit in top
        ]

        latency_ms = (time.perf_counter() - start) * 1000

        return RerankResponse(
            query=request.query,
            reranked=reranked,
            model=self.model_name,
            latency_ms=latency_ms,
            device=self.device
        )