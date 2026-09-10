import os
import re
import json
import requests
from typing import List, Optional, Literal, Dict, Any, TypedDict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from langchain_groq import ChatGroq

load_dotenv()

app = FastAPI(title="LEDGER Financial Agent Service", version="3.0")

# --- Config & Setup ---
RETRIEVAL_SERVICE_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://localhost:8001/api/v1/search/pipeline")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
    temperature=0
) if GROQ_API_KEY else None

# --- 1. Schemas ---
class EvidenceItem(BaseModel):
    document_id: str
    page: int
    section: str

class StructuredAgentOutput(BaseModel):
    answer_type: Literal["direct", "calculated", "multi_span", "insufficient_evidence"]
    evidence: List[EvidenceItem] = Field(default_factory=list)
    params: Dict[str, Any]

class QueryRequest(BaseModel):
    question: str
    document_id: Optional[str] = None

# --- 2. Deterministic Tools ---
@tool
def calculate(expression: str) -> dict:
    """Executes mathematical expressions deterministically using Python."""
    try:
        clean_expr = re.sub(r'[^0-9+\-*/().%\s]', '', expression)
        clean_expr = clean_expr.replace('%', '/100')
        if not clean_expr.strip():
            return {"success": False, "error": "No valid math expression found."}
        result = eval(clean_expr, {"__builtins__": None}, {})
        if isinstance(result, (int, float)):
            result = round(float(result), 4)
        return {"value": result, "formula": clean_expr.strip(), "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}

@tool
def search_documents(query: str, document_id: Optional[str] = None) -> dict:
    """Searches text/chunks across indexed documents."""
    payload = {"query": query, "top_k": 5}
    if document_id:
        payload["filters"] = {"document_id": document_id}
    try:
        resp = requests.post(RETRIEVAL_SERVICE_URL, json=payload, timeout=8)
        if resp.status_code == 200:
            return {"results": resp.json().get("results", []), "success": True}
    except Exception as e:
        return {"results": [], "error": str(e), "success": False}
    return {"results": [], "success": False}

@tool
def search_tables(query: str, document_id: Optional[str] = None) -> dict:
    """Searches financial tables across documents."""
    payload = {"query": query, "top_k": 5, "filters": {"content_type": "table"}}
    if document_id:
        payload["filters"]["document_id"] = document_id
    try:
        resp = requests.post(RETRIEVAL_SERVICE_URL, json=payload, timeout=8)
        if resp.status_code == 200:
            return {"results": resp.json().get("results", []), "success": True}
    except Exception:
        pass
    return {"results": [], "success": False}

@tool
def filter_documents(metadata_key: str, metadata_value: str) -> dict:
    """Filters documents based on metadata parameters."""
    payload = {"query": "", "filters": {metadata_key: metadata_value}}
    try:
        resp = requests.post(RETRIEVAL_SERVICE_URL, json=payload, timeout=8)
        if resp.status_code == 200:
            return {"results": resp.json().get("results", []), "success": True}
    except Exception:
        pass
    return {"results": [], "success": False}

# --- 3. LangGraph State & Reasoning ---
class AgentState(TypedDict):
    question: str
    document_id: Optional[str]
    retrieved_data: List[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
    retry_count: int

def retrieve_node(state: AgentState):
    """Call real search_documents tool."""
    res = search_documents.invoke({"query": state["question"], "document_id": state.get("document_id")})
    return {"retrieved_data": res.get("results", [])}

def prepare_retry_node(state: AgentState):
    """Retry logic node."""
    return {"retry_count": state.get("retry_count", 0) + 1}

def reason_node(state: AgentState):
    """LLM Reasoning Node over retrieved evidence."""
    data = state["retrieved_data"]
    question = state["question"]

    if not data:
        return {
            "final_output": {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {"reason": "No relevant context found in the corpus for the given query."}
            }
        }

    # Format Evidence for Prompting
    context_str = json.dumps(data, indent=2)
    
    prompt = f"""You are a financial analyst agent. Analyze the question and retrieved evidence below.
Return ONLY a JSON matching one of these answer_types: 'direct', 'calculated', 'multi_span', or 'insufficient_evidence'.

Rules:
1. If arithmetic is needed, provide the formula string in params.
2. Structure evidence as array of objects with document_id, page, section.
3. Output strict valid JSON only, no explanatory text.

Question: {question}
Retrieved Context: {context_str}
"""

    if llm:
        try:
            response = llm.invoke(prompt)
            content = response.content.strip()
            # Clean markdown JSON formatting if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(content)
            
            # If calculated, run deterministic python tool
            if parsed.get("answer_type") == "calculated" and "formula" in parsed.get("params", {}):
                calc_res = calculate.invoke(parsed["params"]["formula"])
                parsed["params"]["value"] = calc_res.get("value", 0)
                
            return {"final_output": parsed}
        except Exception:
            pass

    # Fallback structure if LLM response parsing fails
    evidence = []
    for item in data[:2]:
        meta = item.get("metadata", {})
        evidence.append({
            "document_id": meta.get("document_id", "doc_unknown"),
            "page": meta.get("page", 1),
            "section": meta.get("section", "General")
        })

    return {
        "final_output": {
            "answer_type": "direct",
            "evidence": evidence,
            "params": {"value": "Data retrieved from context"}
        }
    }

def decide_next_step(state: AgentState) -> Literal["retry", "reason"]:
    """Conditional Edge Evaluation."""
    data = state.get("retrieved_data", [])
    if not data and state.get("retry_count", 0) < 1:
        return "retry"
    return "reason"

# --- Build LangGraph ---
builder = StateGraph(AgentState)
builder.add_node("retrieve", retrieve_node)
builder.add_node("prepare_retry", prepare_retry_node)
builder.add_node("reason", reason_node)

builder.set_entry_point("retrieve")
builder.add_conditional_edges("retrieve", decide_next_step, {"retry": "prepare_retry", "reason": "reason"})
builder.add_edge("prepare_retry", "retrieve")
builder.add_edge("reason", END)

agent_graph = builder.compile()

# --- 4. FastAPI Endpoint ---
@app.post("/api/v1/agent/query", response_model=StructuredAgentOutput)
async def run_agent(request: QueryRequest):
    try:
        initial_state = {
            "question": request.question,
            "document_id": request.document_id,
            "retrieved_data": [],
            "final_output": None,
            "retry_count": 0
        }
        result = agent_graph.invoke(initial_state)
        return result["final_output"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)