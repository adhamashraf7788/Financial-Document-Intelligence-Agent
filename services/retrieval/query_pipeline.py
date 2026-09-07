import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

from services.retrieval.weaviate import WeaviateStore
from services.retrieval.embedding import BGEM3EmbeddingProvider
from services.reranker.reranker import CrossEncoderReranker
from services.reranker.models import RerankRequest, CandidateChunk


# --- LLM Structured Output Schema ---
class QueryPlan(BaseModel):
    is_complex: bool = Field( description="True if query needs decomposition into sub-questions (e.g., multi-year or cross-document comparison).")
    queries: List[str] = Field(description="List of queries. If simple, contains 1 rewritten search query. If complex, contains decomposed sub-queries.")


class QueryPipeline:
    def __init__(self, weaviate_store: WeaviateStore, embedder: BGEM3EmbeddingProvider, reranker: CrossEncoderReranker, ollama_model: str = "qwen2.5:1.5b"):
        self.store = weaviate_store
        self.embedder = embedder
        self.reranker = reranker

        # Initialize LLM
        llm = OllamaLLM(model=ollama_model, format="json", temperature=0.0)

        planner_prompt = ChatPromptTemplate.from_template(
            "You are a financial query planner.\n"
            "Analyze the user query and output JSON with this exact schema:\n"
            "{{\n"
            '  "is_complex": bool,\n'
            '  "queries": [string]\n'
            "}}\n\n"
            "Rules:\n"
            "1. If simple, return 'is_complex': false and 'queries': [rewritten_search_query].\n"
            "2. If complex (multi-step/comparisons across years or entities), return 'is_complex': true and 2-3 specific sub-queries in 'queries'.\n\n"
            "User Query: {query}"
        )

        self.planner_chain = planner_prompt | llm | QueryPlan.model_validate_json




    def plan_query(self, query: str) -> QueryPlan:
        try:
            return self.planner_chain.invoke({"query": query})
        except Exception:
            # Safe fallback if LLM output fails parsing
            return QueryPlan(is_complex=False, queries=[query])




    def execute_pipeline(self, user_query: str, alpha: float = 0.5, candidates_retrieved: int = 30, top_k: int = 5) -> Dict[str, Any]:
        
        # Query Planning (LLM)
        plan = self.plan_query(user_query)

        # Search (Dense + BM25 Hybrid)
        candidate_map: Dict[str, Dict[str, Any]] = {}

        for sub_query in plan.queries:
            # Generate Embedding of query
            query_vector = self.embedder.generate_embedding(sub_query)

            # Retrieve candidates from Weaviate
            raw_results = self.store.hybrid_search( query_text=sub_query, 
                                                   query_vector=query_vector, 
                                                   alpha=alpha, 
                                                   limit=candidates_retrieved
                                                   )

            # Note: two sub-queries can have the same candidate
            # Deduplicate results (keeping highest score)
            for item in raw_results:
                cid = item["chunk_id"]
                if cid not in candidate_map or item["score"] > candidate_map[cid]["score"]:
                    item["metadata"]["retrieval_method"] = "hybrid"
                    candidate_map[cid] = item

        unique_candidates = list(candidate_map.values())

        if not unique_candidates:
            return {
                "query": user_query,
                "search_mode": "hybrid",
                "alpha": alpha,
                "candidates_retrieved": 0,
                "top_k_returned": 0,
                "results": []
            }


        # Build Rerank Request
        rerank_candidates = [ CandidateChunk(chunk_id=item["chunk_id"],
                                             text=item["text"],
                                             score=item["score"],
                                             metadata=item["metadata"]
                                             ) 
                            for item in unique_candidates
                        ]

        rerank_request = RerankRequest( query=user_query,
                                       candidates=rerank_candidates,
                                       top_k=top_k
                                       )

        # Reranking Output
        rerank_response = self.reranker.rerank(rerank_request)

        # Restructure retrieval pipline Output
        formatted_results = [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "score": chunk.original_score,
                "rerank_logit": chunk.rerank_logit,
                "metadata": chunk.metadata
            }
            for chunk in rerank_response.reranked
        ]

        return {
            "query": user_query,
            "search_mode": "hybrid",
            "alpha": alpha,
            "is_complex": plan.is_complex,
            "generated_queries": plan.queries,
            "candidates_retrieved": len(unique_candidates),
            "top_k_returned": len(formatted_results),
            "results": formatted_results
        }