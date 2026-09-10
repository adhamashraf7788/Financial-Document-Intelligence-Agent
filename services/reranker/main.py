import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from services.reranker.reranker import CrossEncoderReranker
from services.reranker.models import RerankRequest, RerankResponse

reranker: CrossEncoderReranker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global reranker
    model_name = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    batch_size = int(os.getenv("RERANKER_BATCH_SIZE", "32"))
    reranker = CrossEncoderReranker(model_name=model_name, batch_size=batch_size)
    print(f"Reranker loaded: model={model_name}, device={reranker.device}, batch_size={batch_size}")
    yield
    if reranker and reranker.device == "cuda":
        import torch
        torch.cuda.empty_cache()


app = FastAPI(title="Reranker Service", lifespan=lifespan)


@app.post("/rerank", response_model=RerankResponse)
async def rerank_endpoint(request: RerankRequest):
    if not reranker:
        raise HTTPException(status_code=503, detail="Reranker not initialized")
    return reranker.rerank(request)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": reranker.model_name if reranker else "loading",
        "device": reranker.device if reranker else "unknown"
    }