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
    queries = [
        [q.get("query_id"), q.get("question"), q.get("latency_ms"), q.get("status")]
        for q in data.get("recent_queries", [])
    ]

    label_suffix = "" if source == "live" else f" ({source})"
    return (
        f"Total Docs: {stats.get('indexed_documents', 0)}{label_suffix}",
        f"Extracted Tables: {stats.get('total_tables', 0)}{label_suffix}",
        f"Avg Latency: {stats.get('avg_latency_ms', 0)} ms{label_suffix}",
        docs,
        queries,
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
                headers=["Query ID", "Question", "Latency", "Validation Status"],
                label="Recent System Queries",
                interactive=False,
            )

            refresh_btn = gr.Button("Refresh Dashboard Data")
            refresh_btn.click(
                fn=load_dashboard_data,
                inputs=[],
                outputs=[doc_stat_box, table_stat_box, latency_stat_box, doc_table, query_table],
            )
            demo.load(
                fn=load_dashboard_data,
                outputs=[doc_stat_box, table_stat_box, latency_stat_box, doc_table, query_table],
            )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=GRADIO_SHARE)