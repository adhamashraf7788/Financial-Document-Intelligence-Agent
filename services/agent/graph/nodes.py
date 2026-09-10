# import asyncio
# import json
# import logging
# from typing import Literal

# from config import llm, MAX_RETRIEVAL_RETRIES, MAX_LLM_ATTEMPTS
# from tools import calculate, search_documents, search_tables
# from validation import validate_answer
# from graph.state import AgentState

# logger = logging.getLogger("agent_service.graph")


# async def retrieve_node(state: AgentState):
#     """Runs text-chunk search and table search concurrently (issue #2: search_tables
#     was previously defined but never called), then merges + dedupes by chunk_id."""
#     question = state["question"]
#     document_id = state.get("document_id")

#     text_res, table_res = await asyncio.gather(
#         search_documents.ainvoke({"query": question, "document_id": document_id}),
#         search_tables.ainvoke({"query": question, "document_id": document_id}),
#     )

#     merged: dict[str, dict] = {}
#     for res in (text_res, table_res):
#         for item in res.get("results", []):
#             chunk_id = item.get("chunk_id")
#             key = chunk_id if chunk_id is not None else id(item)
#             if key not in merged:
#                 merged[key] = item

#     return {"retrieved_data": list(merged.values())}


# def prepare_retry_node(state: AgentState):
#     """Retry bookkeeping — pure state math, no I/O, stays sync."""
#     return {"retry_count": state.get("retry_count", 0) + 1}


# async def reason_node(state: AgentState):
#     """LLM reasoning over retrieved evidence. Never fabricates an answer:
#     on LLM/parse/validation failure it retries once, then returns
#     insufficient_evidence with the real error surfaced in params.reason."""
#     data = state["retrieved_data"]
#     question = state["question"]

#     if not data:
#         return {
#             "final_output": {
#                 "answer_type": "insufficient_evidence",
#                 "evidence": [],
#                 "params": {"reason": "No relevant context found in the corpus for the given query."},
#             }
#         }

#     context_str = json.dumps(data, indent=2)
#     prompt = f"""You are a financial analyst agent. Analyze the question and retrieved evidence below.
# Return ONLY a JSON matching one of these answer_types: 'direct', 'calculated', 'multi_span', or 'insufficient_evidence'.

# Rules:
# 1. If arithmetic is needed, provide the formula string in params.
# 2. Structure evidence as array of objects with document_id, page, section.
# 3. Output strict valid JSON only, no explanatory text.

# Question: {question}
# Retrieved Context: {context_str}
# """

#     if llm:
#         last_error = "unknown error"
#         for attempt in range(MAX_LLM_ATTEMPTS):
#             try:
#                 response = await llm.ainvoke(prompt)
#                 content = response.content.strip()
#                 if "```json" in content:
#                     content = content.split("```json")[1].split("```")[0].strip()
#                 parsed = json.loads(content)

#                 if parsed.get("answer_type") == "calculated" and "formula" in parsed.get("params", {}):
#                     calc_res = await calculate.ainvoke(parsed["params"]["formula"])
#                     if not calc_res.get("success"):
#                         raise ValueError(f"Calculation failed: {calc_res.get('error')}")
#                     parsed["params"]["value"] = calc_res["value"]

#                 is_valid, err = validate_answer(parsed)
#                 if not is_valid:
#                     raise ValueError(f"Schema validation failed: {err}")

#                 return {"final_output": parsed}

#             except Exception as e:
#                 last_error = str(e)
#                 logger.warning("reason_node attempt %d failed: %s", attempt + 1, last_error)
#                 continue

#         return {
#             "final_output": {
#                 "answer_type": "insufficient_evidence",
#                 "evidence": [],
#                 "params": {"reason": f"LLM failed to produce a valid answer after retry: {last_error}"},
#             }
#         }

#     return {
#         "final_output": {
#             "answer_type": "insufficient_evidence",
#             "evidence": [],
#             "params": {"reason": "LLM is not configured (GROQ_API_KEY missing)."},
#         }
#     }


# def decide_next_step(state: AgentState) -> Literal["retry", "reason"]:
#     data = state.get("retrieved_data", [])
#     if not data and state.get("retry_count", 0) < MAX_RETRIEVAL_RETRIES:
#         return "retry"
#     return "reason"





import asyncio
import json
import logging
from typing import Literal

from config import llm, MAX_RETRIEVAL_RETRIES, MAX_LLM_ATTEMPTS
from tools import calculate, search_documents, search_tables
from validation import validate_answer
from graph.state import AgentState

logger = logging.getLogger("agent_service.graph")


async def retrieve_node(state: AgentState):
    """Runs text-chunk search and table search concurrently (issue #2: search_tables
    was previously defined but never called), then merges + dedupes by chunk_id."""
    question = state["question"]
    document_id = state.get("document_id")

    text_res, table_res = await asyncio.gather(
        search_documents.ainvoke({"query": question, "document_id": document_id}),
        search_tables.ainvoke({"query": question, "document_id": document_id}),
    )

    merged: dict[str, dict] = {}
    for res in (text_res, table_res):
        for item in res.get("results", []):
            chunk_id = item.get("chunk_id")
            key = chunk_id if chunk_id is not None else id(item)
            if key not in merged:
                merged[key] = item

    return {"retrieved_data": list(merged.values())}


def prepare_retry_node(state: AgentState):
    """Retry bookkeeping — pure state math, no I/O, stays sync."""
    return {"retry_count": state.get("retry_count", 0) + 1}


async def reason_node(state: AgentState):
    """LLM reasoning over retrieved evidence. Never fabricates an answer:
    on LLM/parse/validation failure it retries once, then returns
    insufficient_evidence with the real error surfaced in params.reason."""
    data = state["retrieved_data"]
    question = state["question"]

    if not data:
        return {
            "final_output": {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {"reason": "No relevant context found in the corpus for the given query."},
            }
        }

    context_str = json.dumps(data, indent=2)
    prompt = f"""You are a financial analyst agent. Analyze the question and retrieved evidence below.
Return ONLY a single JSON object — no markdown fences, no explanatory text before or after.

Choose exactly one answer_type and match its required params exactly:

- "direct": params = {{"value": <string or number>}}. evidence must have >= 1 citation.
- "calculated": params = {{"value": <number>, "formula": <string>}}. evidence must have >= 1 citation.
- "multi_span": params = {{"values": [<string>, <string>, ...]}} (>= 2 items). evidence must have >= 1 citation.
- "insufficient_evidence": params = {{"reason": <string explaining what's missing>}}. evidence may be [].
  IMPORTANT: even when you choose insufficient_evidence, params.reason is REQUIRED — never return params: {{}}.

evidence is always an array of objects: {{"document_id": ..., "page": ..., "section": ...}}.

Question: {question}
Retrieved Context: {context_str}

Respond with only the JSON object.
"""

    if llm:
        last_error = "unknown error"
        for attempt in range(MAX_LLM_ATTEMPTS):
            try:
                response = await llm.ainvoke(prompt)
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                parsed = json.loads(content)

                # Defensive repair: model chose insufficient_evidence but forgot
                # params.reason (schema-invalid but clearly not a hallucinated
                # answer) — fill a generic reason rather than burning a retry.
                if parsed.get("answer_type") == "insufficient_evidence" and not parsed.get("params", {}).get("reason"):
                    parsed.setdefault("params", {})["reason"] = (
                        "Model indicated insufficient evidence but did not provide a specific reason."
                    )

                if parsed.get("answer_type") == "calculated" and "formula" in parsed.get("params", {}):
                    calc_res = await calculate.ainvoke(parsed["params"]["formula"])
                    if not calc_res.get("success"):
                        raise ValueError(f"Calculation failed: {calc_res.get('error')}")
                    parsed["params"]["value"] = calc_res["value"]

                is_valid, err = validate_answer(parsed)
                if not is_valid:
                    raise ValueError(f"Schema validation failed: {err}")

                return {"final_output": parsed}

            except Exception as e:
                last_error = str(e)
                logger.warning("reason_node attempt %d failed: %s", attempt + 1, last_error)
                continue

        return {
            "final_output": {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {"reason": f"LLM failed to produce a valid answer after retry: {last_error}"},
            }
        }

    return {
        "final_output": {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "LLM is not configured (GROQ_API_KEY missing)."},
        }
    }


def decide_next_step(state: AgentState) -> Literal["retry", "reason"]:
    data = state.get("retrieved_data", [])
    if not data and state.get("retry_count", 0) < MAX_RETRIEVAL_RETRIES:
        return "retry"
    return "reason"