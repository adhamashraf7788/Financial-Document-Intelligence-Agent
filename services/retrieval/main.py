from fastapi import FastAPI, HTTPException, status, Query
import uvicorn
from shared.schemas import DocumentProcessorResponse
from services.retrieval.chunker import DocumentChunker
from services.retrieval.embedding import BGEM3EmbeddingProvider
from services.retrieval.weaviate import WeaviateStore
from contextlib import asynccontextmanager
from services.reranker.reranker import CrossEncoderReranker
from services.retrieval.query_pipeline import QueryPipeline

# Global service holders
chunker = None
embedder = None
weaviate_store = None
reranker = None
pipeline = None



@asynccontextmanager
async def lifespan(app: FastAPI):
    global chunker, embedder, weaviate_store, reranker, pipeline
    print("Loading embedding model and connecting to vector DB...")
    chunker = DocumentChunker()
    embedder = BGEM3EmbeddingProvider()
    weaviate_store = WeaviateStore(port=8085, grpc_port= 50052)

    print("Initializing Reranker and Query Pipeline...")
    reranker = CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", batch_size=32)
    pipeline = QueryPipeline( weaviate_store=weaviate_store,
                             embedder=embedder,
                             reranker=reranker
                             )

    print("Services initialized successfully.")
    yield
    if weaviate_store:
        weaviate_store.close()

app = FastAPI(title="Retrieval Service - Chunking", lifespan=lifespan)

# chunking (test route)
@app.post("/test-chunking")
async def test_chunking(parsed_doc: DocumentProcessorResponse):

    chunks = chunker.process_parsed_document(parsed_doc)
    return {
        "document_id": parsed_doc.document_id,
        "total_chunks_created": len(chunks),
        "chunks": [chunk.dict() for chunk in chunks]
    }



# chuncks the document
# then generates the embeddings 
# passes them to weaviate
@app.post("/index-document")
async def index_document(parsed_doc: DocumentProcessorResponse):

    chunks = chunker.process_parsed_document(parsed_doc)
    if not chunks:
        return {"status": "success", "indexed_chunks": 0}

    texts = [chunk.text for chunk in chunks]
    embeddings = embedder.generate_embeddings(texts)
    
    weaviate_store.insert_chunks(chunks, embeddings)
    
    return {
        "document_id": parsed_doc.document_id,
        "total_chunks_indexed": len(chunks)
    }



# Gets stored chunks from the vector DB.
@app.get("/documents/all")
async def get_all_documents(limit: int = 100):

    if not weaviate_store:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail="Database service not initialized"
                            )
    
    results = weaviate_store.fetch_all_chunks(limit=limit)
    return {
        "total_retrieved": len(results),
        "results": results
    }



# bm25 search only (test route)
@app.post("/search/bm25")
async def search_bm25( query: str, candidates_retrieved: int = 30, top_k_returned: int = 5):

    if not weaviate_store:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail="Weaviate service is not initialized"
                            )

    results = weaviate_store.bm25_search(query_text=query, 
                                         limit=candidates_retrieved
                                         )

    top_results = results[:top_k_returned]
    
    # Tag retrieval method
    for item in top_results:
        item["metadata"]["retrieval_method"] = "bm25"

    return {
        "query": query,
        "search_mode": "bm25",
        "candidates_retrieved": len(results),
        "top_k_returned": len(top_results),
        "results": top_results
    }



# vector search only (test route)
@app.post("/search/vector")
async def search_vector(query: str, candidates_retrieved: int = 30, top_k_returned: int = 5):

    if not weaviate_store or not embedder:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail="Retrieval or embedding service is not initialized"
                            )

    query_vector = embedder.generate_embedding(query)
    results = weaviate_store.vector_search(query_vector=query_vector, 
                                           limit=candidates_retrieved
                                           )

    top_results = results[:top_k_returned]
    
    # Tag retrieval method
    for item in top_results:
        item["metadata"]["retrieval_method"] = "dense"

    return {
        "query": query,
        "search_mode": "vector",
        "candidates_retrieved": len(results),
        "top_k_returned": len(top_results),
        "results": top_results
    }



# hybrid search (test route)
@app.post("/search/hybrid")
async def search_hybrid(
    query: str,
    alpha: float = Query(0.5, ge=0.0, le=1.0, description="Alpha weighting: 0.0 = Pure BM25, 1.0 = Pure Vector"),
    candidates_retrieved: int = 30,
    top_k_returned: int = 5
):
    if not weaviate_store or not embedder:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail="Retrieval or embedding service is not initialized"
                            )

    query_vector = embedder.generate_embedding(query)
    results = weaviate_store.hybrid_search(query_text=query,
                                        query_vector=query_vector, 
                                        alpha=alpha, 
                                        limit=candidates_retrieved
                                        )

    top_results = results[:top_k_returned]
    
    # Tag retrieval method
    for item in top_results:
        item["metadata"]["retrieval_method"] = "hybrid"

    return {
        "query": query,
        "search_mode": "hybrid",
        "alpha": alpha,
        "candidates_retrieved": len(results),
        "top_k_returned": len(top_results),
        "results": top_results
    }



# Full retrieval pipeline
@app.post("/search/pipeline")
async def execute_query_pipeline(
    query: str,
    alpha: float = Query(0.5, ge=0.0, le=1.0, description="Alpha weighting: 0.0 = Pure BM25, 1.0 = Pure Vector"),
    candidates_retrieved: int = 30,
    top_k_returned: int = 5
):
    if not pipeline:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                            detail="Query pipeline is not initialized"
                            )

    return pipeline.execute_pipeline(user_query=query,
                                     alpha=alpha,
                                     candidates_retrieved=candidates_retrieved,
                                     top_k=top_k_returned
                                     )


# Launching Test server
if __name__ == '__main__':
    uvicorn.run("services.retrieval.main:app", host="0.0.0.0", port=8000, reload=True)