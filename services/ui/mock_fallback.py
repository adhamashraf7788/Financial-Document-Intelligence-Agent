import json
import re
import logging

from config import MOCK_UI_PATH

logger = logging.getLogger("ui_service.mock_fallback")

_DEFAULT_MOCK_DASHBOARD = {
    "dashboard_stats": {"indexed_documents": 3, "total_tables": 7, "avg_latency_ms": 425},
    "indexed_documents": [
        {"document_id": "doc_017", "filename": "AAPL_Q3_2020.pdf", "pages": 3, "tables": 2},
        {"document_id": "doc_022", "filename": "MSFT_Q4_2021.pdf", "pages": 2, "tables": 1},
        {"document_id": "doc_041", "filename": "AMZN_Annual_2020.pdf", "pages": 5, "tables": 4},
    ],
    "recent_queries": [
        {"query_id": "q_001", "question": "What was operating income in 2020?", "latency_ms": "340 ms", "status": "SUCCESS"},
        {"query_id": "q_002", "question": "Calculate percentage change in R&D", "latency_ms": "510 ms", "status": "SUCCESS"},
    ],
}


def load_mock_dashboard() -> dict:
    """Loads dashboard mock data from disk, falling back to an inline default.
    Caller is responsible for labeling this as mock data in the UI."""
    try:
        with open(MOCK_UI_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.info("Mock UI data file unavailable (%s), using inline default.", e)
        return _DEFAULT_MOCK_DASHBOARD


def get_mock_answer(question: str, document_id: str) -> dict:
    """Heuristic demo answer, strictly matching the Strict Answer Schema shape.
    NOTE: this is illustrative only — 'calculated' answers here echo a placeholder
    value, they are not computed from real evidence. Never present this to a user
    as if it came from the real agent (issue #1) without a visible mock/demo label."""
    doc = document_id if document_id else "doc_017"
    q_lower = question.lower()

    has_math_op = (
        bool(re.search(r"[\+\-\*/%]", question))
        or "calculate" in q_lower
        or "percentage" in q_lower
    )
    is_list_question = q_lower.startswith(("list", "which")) or " which " in q_lower
    is_unknown_question = "unknown" in q_lower or "missing" in q_lower

    if is_unknown_question:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "Metric not found in indexed corpus. (mock response)"},
        }
    if is_list_question:
        return {
            "answer_type": "multi_span",
            "evidence": [{"document_id": doc, "page": 3, "section": "Breakdown"}],
            "params": {"values": ["Marketing", "R&D", "Logistics"]},
        }
    if has_math_op:
        return {
            "answer_type": "calculated",
            "evidence": [{"document_id": doc, "page": 2, "section": "Financial Calculations"}],
            "params": {"value": 3.0, "formula": "(mock — not computed from real evidence)"},
        }

    return {
        "answer_type": "direct",
        "evidence": [{"document_id": doc, "page": 1, "section": "Income Statement"}],
        "params": {"value": "$142.5M (mock)"},
    }
