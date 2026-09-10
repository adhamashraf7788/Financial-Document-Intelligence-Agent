from typing import List, Optional


def format_citations(evidence_list: List[dict]) -> str:
    """Formats mandatory document and page citations."""
    if not evidence_list:
        return "\n\n*No citations provided or insufficient evidence.*"

    citations = ["\n\n---\n### Source Citations (Grounded Evidence):"]
    for ev in evidence_list:
        doc = ev.get("document_id", "N/A")
        page = ev.get("page", "N/A")
        section = ev.get("section", "General")
        citations.append(f"- **Doc ID:** `{doc}` | **Page:** `{page}` | **Section:** *{section}*")
    return "\n".join(citations)


def format_source_banner(source: str, error: Optional[str] = None) -> str:
    """Explicit, visible banner distinguishing live agent answers from mock/demo
    or error states (issue #1 / #6) — previously these all rendered identically."""
    if source == "live":
        return ""
    if source == "mock":
        return (
            "> ⚠️ **Demo mode:** the orchestrator is unreachable"
            + (f" ({error})" if error else "")
            + ". Showing an illustrative mock answer — not a real, evidence-backed result.\n\n"
        )
    if source == "error":
        return f"> ❌ **Request failed:** {error or 'unknown error'}\n\n"
    return ""


def format_answer(res_data: dict, source: str, error: Optional[str] = None) -> str:
    answer_type = res_data.get("answer_type", "N/A")
    params = res_data.get("params", {})
    evidence = res_data.get("evidence", [])

    formatted_res = format_source_banner(source, error)
    formatted_res += f"### Answer Output\n\n**Answer Type:** `{answer_type}`\n\n"

    if answer_type == "direct":
        formatted_res += f"**Result:** {params.get('value', 'N/A')}\n\n"
    elif answer_type == "calculated":
        formatted_res += f"**Computed Value:** `{params.get('value', 'N/A')}`\n\n"
        formatted_res += f"**Formula Used:** `{params.get('formula', 'N/A')}`\n\n"
    elif answer_type == "multi_span":
        values = params.get("values", [])
        formatted_res += "**Retrieved Items:**\n" + "\n".join(f"- {v}" for v in values) + "\n\n"
    elif answer_type == "insufficient_evidence":
        formatted_res += f"**Insufficient Evidence:** {params.get('reason', 'No detail provided.')}\n\n"

    formatted_res += format_citations(evidence)
    return formatted_res
