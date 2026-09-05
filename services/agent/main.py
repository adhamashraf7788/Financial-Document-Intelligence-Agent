import os
import re
from typing import List, Optional, Literal, Dict, Any, TypedDict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langchain_core.tools import tool

load_dotenv()

app = FastAPI(title="LEDGER Financial Agent (Mock Service)", version="2.0")

# --- 1. Schemas الملتزمة بالمستند ---

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

# --- 2. Deterministic Tools (مع Mock للـ Retrieval) ---

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

        return {
            "value": result,
            "formula": clean_expr.strip(),
            "success": True
        }
    except Exception as e:
        return {
            "error": f"Failed to evaluate expression: {str(e)}",
            "success": False
        }

def mock_retrieval_api(query: str, document_id: Optional[str] = None) -> Dict[str, Any]:
    """محاكاة استجابة الـ retrieval-api الخاص بزمايلك"""
    q = query.lower()
    doc = document_id or "doc_041"
    
    if any(kw in q for kw in ["unknown", "restructuring", "missing", "not found"]):
        return {"found": False, "evidence": []}
    elif any(kw in q for kw in ["categories", "list", "expenses", "which"]):
        return {
            "found": True,
            "type": "multi_span",
            "evidence": [{"document_id": doc, "page": 3, "section": "Operating Expenses"}],
            "data": ["Marketing", "R&D", "Logistics"]
        }
    elif any(kw in q for kw in ["calculate", "%", "sum", "difference", "3875", "3410"]):
        return {
            "found": True,
            "type": "calculated",
            "evidence": [
                {"document_id": doc, "page": 2, "section": "Operating Expenses"},
                {"document_id": doc, "page": 2, "section": "Operating Expenses"}
            ],
            "expr": "(3875-3410)/3410*100"
        }
    else:
        return {
            "found": True,
            "type": "direct",
            "evidence": [{"document_id": doc, "page": 1, "section": "Income Statement"}],
            "data": "$142.5M"
        }

# --- 3. LangGraph Dynamic State Machine ---

class AgentState(TypedDict):
    question: str
    document_id: Optional[str]
    retrieved_data: Dict[str, Any]
    final_output: Optional[Dict[str, Any]]
    retry_count: int

def retrieve_node(state: AgentState):
    """عقدة استدعاء خدمة البحث (حسب رد الـ Mock)"""
    res = mock_retrieval_api(state["question"], state.get("document_id"))
    return {"retrieved_data": res}

def reason_and_tool_node(state: AgentState):
    """عقدة اتخاذ القرار وتنفيذ الأدوات الحسابية"""
    data = state["retrieved_data"]
    
    if not data.get("found"):
        output = {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "No document in the indexed corpus reports the requested metric."}
        }
    elif data.get("type") == "calculated":
        expr = data.get("expr", "0")
        calc_res = calculate.invoke(expr)
        output = {
            "answer_type": "calculated",
            "evidence": data["evidence"],
            "params": {
                "value": calc_res.get("value", 0),
                "formula": calc_res.get("formula", expr)
            }
        }
    elif data.get("type") == "multi_span":
        output = {
            "answer_type": "multi_span",
            "evidence": data["evidence"],
            "params": {"values": data["data"]}
        }
    else:
        output = {
            "answer_type": "direct",
            "evidence": data["evidence"],
            "params": {"value": data["data"]}
        }
        
    return {"final_output": output}

def prepare_retry_node(state: AgentState):
    """عقدة الـ Retry عند ضعف الأدلة"""
    return {"retry_count": state.get("retry_count", 0) + 1}

def decide_next_step(state: AgentState) -> Literal["reason", "retry", "end"]:
    """مسارات التفرع الشرطي في الـ Graph"""
    data = state.get("retrieved_data", {})
    if not data.get("found") and state.get("retry_count", 0) < 1:
        return "retry"
    return "reason"

# --- بناء الـ Graph الشرطي ---

builder = StateGraph(AgentState)

builder.add_node("retrieve", retrieve_node)
builder.add_node("prepare_retry", prepare_retry_node)
builder.add_node("reason", reason_and_tool_node)

builder.set_entry_point("retrieve")

builder.add_conditional_edges(
    "retrieve",
    decide_next_step,
    {
        "retry": "prepare_retry",
        "reason": "reason"
    }
)

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
            "retrieved_data": {},
            "final_output": None,
            "retry_count": 0
        }
        
        result = agent_graph.invoke(initial_state)
        return result["final_output"]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)