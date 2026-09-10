import ast
import operator
import httpx
from typing import Optional
from langchain_core.tools import tool

from config import RETRIEVAL_SERVICE_URL, HTTP_TIMEOUT

# Shared async client (issue #7): reused across requests instead of
# opening/closing a new connection pool per call.
_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    return _client


async def close_http_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# --- Safe arithmetic evaluator (issue #1: no eval()) ---
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression element: {type(node).__name__}")


def safe_arithmetic_eval(expression: str) -> float:
    """Parses and evaluates a restricted arithmetic expression via the AST,
    supporting only numeric literals and +, -, *, /, %, **, parens, unary +/-.
    Raises ValueError on anything else (names, calls, attributes, etc.)."""
    tree = ast.parse(expression, mode="eval")
    return _safe_eval(tree)


# --- 2. Deterministic Tools ---

@tool
async def calculate(expression: str) -> dict:
    """Executes mathematical expressions deterministically and safely."""
    try:
        clean_expr = expression.replace("%", "/100")
        if not clean_expr.strip():
            return {"success": False, "error": "No valid math expression found."}
        result = safe_arithmetic_eval(clean_expr)
        result = round(float(result), 4)
        return {"value": result, "formula": clean_expr.strip(), "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}


@tool
async def search_documents(query: str, document_id: Optional[str] = None) -> dict:
    """Searches text/chunks across indexed documents."""
    payload = {"query": query, "top_k": 5}
    if document_id:
        payload["filters"] = {"document_id": document_id}
    try:
        resp = await get_http_client().post(RETRIEVAL_SERVICE_URL, json=payload)
        if resp.status_code == 200:
            return {"results": resp.json().get("results", []), "success": True}
    except Exception as e:
        return {"results": [], "error": str(e), "success": False}
    return {"results": [], "success": False}


@tool
async def search_tables(query: str, document_id: Optional[str] = None) -> dict:
    """Searches financial tables across documents."""
    payload = {"query": query, "top_k": 5, "filters": {"content_type": "table"}}
    if document_id:
        payload["filters"]["document_id"] = document_id
    try:
        resp = await get_http_client().post(RETRIEVAL_SERVICE_URL, json=payload)
        if resp.status_code == 200:
            return {"results": resp.json().get("results", []), "success": True}
    except Exception as e:
        return {"results": [], "error": str(e), "success": False}
    return {"results": [], "success": False}


@tool
async def filter_documents(metadata_key: str, metadata_value: str) -> dict:
    """Filters documents based on metadata parameters."""
    payload = {"query": "", "filters": {metadata_key: metadata_value}}
    try:
        resp = await get_http_client().post(RETRIEVAL_SERVICE_URL, json=payload)
        if resp.status_code == 200:
            return {"results": resp.json().get("results", []), "success": True}
    except Exception as e:
        return {"results": [], "error": str(e), "success": False}
    return {"results": [], "success": False}
