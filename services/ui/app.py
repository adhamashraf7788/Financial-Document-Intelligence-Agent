import json
import os
import re
import requests
import gradio as gr

MOCK_UI_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../mock-data/ui_service_mock.json")
)


def load_dashboard_data():
    """Loads dashboard statistics, document list, and recent queries."""
    orchestrator_url = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://localhost:8000")
    try:
        response = requests.get(f"{orchestrator_url}/api/v1/dashboard", timeout=3)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("dashboard_stats", {})
            docs = [
                [
                    d.get("document_id"),
                    d.get("filename"),
                    d.get("pages"),
                    d.get("tables"),
                ]
                for d in data.get("indexed_documents", [])
            ]
            queries = [
                [
                    q.get("query_id"),
                    q.get("question"),
                    q.get("latency_ms"),
                    q.get("status"),
                ]
                for q in data.get("recent_queries", [])
            ]
            return (
                f"Total Docs: {stats.get('indexed_documents', 0)}",
                f"Extracted Tables: {stats.get('total_tables', 0)}",
                f"Avg Latency: {stats.get('avg_latency_ms', 0)} ms",
                docs,
                queries,
            )
    except Exception:
        pass

    try:
        with open(MOCK_UI_PATH, "r") as f:
            data = json.load(f)
            stats = data.get("dashboard_stats", {})
            docs = [
                [
                    d.get("document_id"),
                    d.get("filename"),
                    d.get("pages"),
                    d.get("tables"),
                ]
                for d in data.get("indexed_documents", [])
            ]
            queries = [
                [
                    q.get("query_id"),
                    q.get("question"),
                    q.get("latency_ms"),
                    q.get("status"),
                ]
                for q in data.get("recent_queries", [])
            ]
            return (
                f"Total Docs: {stats.get('indexed_documents', 0)}",
                f"Extracted Tables: {stats.get('total_tables', 0)}",
                f"Avg Latency: {stats.get('avg_latency_ms', 0)} ms",
                docs,
                queries,
            )
    except Exception:
        mock_docs = [
            ["doc_017", "AAPL_Q3_2020.pdf", 3, 2],
            ["doc_022", "MSFT_Q4_2021.pdf", 2, 1],
            ["doc_041", "AMZN_Annual_2020.pdf", 5, 4],
        ]
        mock_queries = [
            ["q_001", "What was operating income in 2020?", "340 ms", "SUCCESS"],
            ["q_002", "Calculate percentage change in R&D", "510 ms", "SUCCESS"],
        ]
        return (
            "Total Docs: 3",
            "Extracted Tables: 7",
            "Avg Latency: 425 ms",
            mock_docs,
            mock_queries,
        )


def format_citations(evidence_list):
    """Formats mandatory document and page citations."""
    if not evidence_list:
        return "\n\n*No citations provided or insufficient evidence.*"

    citations = ["\n\n---\n### Source Citations (Grounded Evidence):"]
    for ev in evidence_list:
        doc = ev.get("document_id", "N/A")
        page = ev.get("page", "N/A")
        section = ev.get("section", "General")
        citations.append(
            f"- **Doc ID:** `{doc}` | **Page:** `{page}` | **Section:** *{section}*"
        )
    return "\n".join(citations)


def get_mock_fallback(question, document_id):
    """Fallback Mock response strictly matching schema."""
    doc = document_id if document_id else "doc_017"
    q_lower = question.lower()

    has_math_op = (
        bool(re.search(r"[\+\-\*/%]", question))
        or "calculate" in q_lower
        or "sum" in q_lower
        or "difference" in q_lower
    )

    if has_math_op:
        return {
            "answer_type": "calculated",
            "evidence": [
                {
                    "document_id": doc,
                    "page": 2,
                    "section": "Financial Calculations",
                }
            ],
            "params": {"value": 3.0, "formula": question.strip()},
        }
    elif "list" in q_lower or "which" in q_lower:
        return {
            "answer_type": "multi_span",
            "evidence": [
                {"document_id": doc, "page": 3, "section": "Breakdown"}
            ],
            "params": {"values": ["Marketing", "R&D", "Logistics"]},
        }
    elif "unknown" in q_lower or "missing" in q_lower:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "Metric not found in indexed corpus."},
        }

    return {
        "answer_type": "direct",
        "evidence": [
            {"document_id": doc, "page": 1, "section": "Income Statement"}
        ],
        "params": {"value": "$142.5M"},
    }


def process_query(user_message, document_id):
    if not user_message or not user_message.strip():
        return "Please enter a valid question.", "N/A", "{}"

    orchestrator_url = os.getenv(
        "ORCHESTRATOR_SERVICE_URL", "http://localhost:8000/api/v1/query"
    )
    payload = {"question": user_message}
    if document_id and document_id.strip():
        payload["document_id"] = document_id.strip()

    try:
        response = requests.post(orchestrator_url, json=payload, timeout=15)
        if response.status_code == 200:
            res_data = response.json()
        else:
            res_data = get_mock_fallback(user_message, document_id)
    except Exception:
        res_data = get_mock_fallback(user_message, document_id)

    answer_type = res_data.get("answer_type", "N/A")
    params = res_data.get("params", {})
    evidence = res_data.get("evidence", [])

    formatted_res = f"### Answer Output\n\n**Answer Type:** `{answer_type}`\n\n"

    if answer_type == "direct":
        formatted_res += f"**Result:** {params.get('value', 'N/A')}\n\n"
    elif answer_type == "calculated":
        formatted_res += f"**Computed Value:** `{params.get('value', 'N/A')}`\n\n"
        formatted_res += f"**Formula Used:** `{params.get('formula', 'N/A')}`\n\n"
    elif answer_type == "multi_span":
        values = params.get("values", [])
        formatted_res += "**Retrieved Items:**\n" + "\n".join([f"- {v}" for v in values]) + "\n\n"
    elif answer_type == "insufficient_evidence":
        formatted_res += f"**Insufficient Evidence:** {params.get('reason', 'No detail provided.')}\n\n"

    formatted_res += format_citations(evidence)

    return formatted_res, answer_type, json.dumps(res_data, indent=2)


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
                    answer_type_output = gr.Textbox(
                        label="Detected Answer Type", interactive=False
                    )
                    raw_json_output = gr.Code(
                        label="Full Schema Response (JSON)", language="json"
                    )

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
    share_enabled = os.getenv("GRADIO_SHARE", "False").lower() == "true"
    demo.launch(server_name="0.0.0.0", server_port=7860, share=share_enabled)