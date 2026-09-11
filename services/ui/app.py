import json
import logging
import os

import gradio as gr

from config import GRADIO_SHARE
from api_client import fetch_dashboard, fetch_health, submit_query
from mock_fallback import load_mock_dashboard, get_mock_answer
from formatting import format_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ui_service.app")

# When false, a failed orchestrator call surfaces as a plain error instead of
# falling back to illustrative mock data. Default true keeps local/demo usage
# working out of the box; set to "false" in any environment where a mock
# answer must never be shown to a real user.
ALLOW_MOCK_FALLBACK = os.getenv("UI_ALLOW_MOCK_FALLBACK", "True").lower() == "true"


def format_chunk_details(chunk_details: list) -> str:
    """Format chunk details for display in the dashboard."""
    if not chunk_details:
        return "No chunks retrieved"
    
    lines = []
    for chunk in chunk_details:
        chunk_id = chunk.get("chunk_id", "N/A")[:20] + "..." if len(chunk.get("chunk_id", "")) > 20 else chunk.get("chunk_id", "N/A")
        rank = chunk.get("rank", "N/A")
        score = chunk.get("score")
        rerank_logit = chunk.get("rerank_logit")
        doc_id = chunk.get("document_id", "N/A")[:15] + "..." if len(chunk.get("document_id", "")) > 15 else chunk.get("document_id", "N/A")
        page = chunk.get("page", "N/A")
        section = chunk.get("section", "N/A")[:20] + "..." if len(chunk.get("section", "")) > 20 else chunk.get("section", "N/A")
        content_type = chunk.get("content_type", "N/A")
        
        score_str = f"{score:.4f}" if score is not None else "N/A"
        rerank_str = f"{rerank_logit:.4f}" if rerank_logit is not None else "N/A"
        
        lines.append(f"  Rank {rank}: {chunk_id} | Score: {score_str} | Rerank: {rerank_str} | Doc: {doc_id} | Page: {page} | Section: {section} | Type: {content_type}")
    return "\n".join(lines)


async def load_dashboard_data():
    data, error = await fetch_dashboard()
    source = "live"
    if data is None:
        source = "mock" if ALLOW_MOCK_FALLBACK else "error"
        data = load_mock_dashboard() if ALLOW_MOCK_FALLBACK else {}
        logger.warning("Dashboard load falling back to %s (%s)", source, error)

    stats = data.get("dashboard_stats", {})
    docs = [
        [d.get("document_id"), d.get("filename"), d.get("pages"), d.get("tables")]
        for d in data.get("indexed_documents", [])
    ]
    
    # Enhanced query table with chunk details
    queries = []
    chunk_details_map = {}  # query_id -> formatted chunk details
    for q in data.get("recent_queries", []):
        query_id = q.get("query_id", "N/A")
        question = q.get("question", "N/A")
        latency = q.get("latency_ms", "N/A")
        retry_count = q.get("retry_count", 0)
        answer_type = q.get("answer_type", "N/A")
        status = q.get("status", "N/A")
        
        queries.append([query_id, question, f"{latency} ms", retry_count, answer_type, status])
        
        # Store chunk details for this query
        chunk_details = q.get("chunk_details", [])
        chunk_details_map[query_id] = format_chunk_details(chunk_details)

    label_suffix = "" if source == "live" else f" ({source})"
    return (
        f"Total Docs: {stats.get('indexed_documents', 0)}{label_suffix}",
        f"Extracted Tables: {stats.get('total_tables', 0)}{label_suffix}",
        f"Avg Latency: {stats.get('avg_latency_ms', 0)} ms{label_suffix}",
        docs,
        queries,
        format_chunk_details_display(chunk_details_map),
    )


async def process_query(user_message: str, document_id: str):
    if not user_message or not user_message.strip():
        return "Please enter a valid question.", "N/A", "{}"

    health, _ = await fetch_health()
    if health and not health.get("checks", {}).get("llm_configured", True):
        return (
            "⚠️ **GROQ_API_KEY is not set on agent-service.**\n\n"
            "Add it to your `.env` file at the repo root and restart with "
            "`docker compose up --build`.",
            "N/A",
            "{}",
        )

    res_data, error = await submit_query(user_message, document_id)
    source = "live"

    if res_data is None:
        if ALLOW_MOCK_FALLBACK:
            source = "mock"
            res_data = get_mock_answer(user_message, document_id)
            logger.warning("Query falling back to mock answer (%s)", error)
        else:
            source = "error"
            res_data = {"answer_type": "N/A", "evidence": [], "params": {}}

    formatted_res = format_answer(res_data, source, error)
    answer_type = res_data.get("answer_type", "N/A")
    return formatted_res, f"{answer_type} [{source}]", json.dumps(res_data, indent=2)


def format_chunk_details_display(chunk_details_map: dict) -> str:
    """Format all chunk details for display."""
    if not chunk_details_map:
        return "No query history available."
    
    output = []
    for query_id, details in chunk_details_map.items():
        output.append(f"### Query: {query_id}")
        output.append(details)
        output.append("")
    return "\n".join(output)


with gr.Blocks(title="LEDGER - Financial Intelligence Agent") as demo:
    gr.Markdown("# LEDGER: Financial Document Intelligence")

    with gr.Tabs():
        with gr.Tab("Financial Assistant"):
            with gr.Row():
                with gr.Column(scale=3):
                    question_input = gr.Textbox(
                        label="Your Question",
                        placeholder="Ask across corpus (e.g. What was operating income in 2020?)",
                        lines=2,
                    )
                    doc_id_input = gr.Textbox(
                        label="Document ID Scope (Optional)",
                        placeholder="Leave blank for Corpus-wide search",
                    )
                    submit_btn = gr.Button("Submit Query", variant="primary")
                    answer_output = gr.Markdown(label="Agent Response")

                with gr.Column(scale=2):
                    gr.Markdown("### Verified Execution Metadata")
                    answer_type_output = gr.Textbox(label="Detected Answer Type", interactive=False)
                    raw_json_output = gr.Code(label="Full Schema Response (JSON)", language="json")

            submit_btn.click(
                fn=process_query,
                inputs=[question_input, doc_id_input],
                outputs=[answer_output, answer_type_output, raw_json_output],
            )
            question_input.submit(
                fn=process_query,
                inputs=[question_input, doc_id_input],
                outputs=[answer_output, answer_type_output, raw_json_output],
            )

        with gr.Tab("Corpus Dashboard"):
            with gr.Row():
                doc_stat_box = gr.Textbox(label="Indexed Files", interactive=False)
                table_stat_box = gr.Textbox(label="Table Extraction", interactive=False)
                latency_stat_box = gr.Textbox(label="Performance Metric", interactive=False)

            gr.Markdown("### Indexed Document Corpus")
            doc_table = gr.Dataframe(
                headers=["Document ID", "Filename", "Pages", "Extracted Tables"],
                label="Corpus Document List",
                interactive=False,
            )

            gr.Markdown("### Recent Execution Logs")
            query_table = gr.Dataframe(
                headers=["Query ID", "Question", "Latency", "Retries", "Answer Type", "Status"],
                label="Recent System Queries",
                interactive=False,
            )

            gr.Markdown("### Retrieved Chunk Details (Per Query)")
            chunk_details_display = gr.Markdown(label="Chunk Details")

            refresh_btn = gr.Button("Refresh Dashboard Data")
            refresh_btn.click(
                fn=load_dashboard_data,
                inputs=[],
                outputs=[doc_stat_box, table_stat_box, latency_stat_box, doc_table, query_table, chunk_details_display],
            )
            demo.load(
                fn=load_dashboard_data,
                outputs=[doc_stat_box, table_stat_box, latency_stat_box, doc_table, query_table, chunk_details_display],
            )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=GRADIO_SHARE)