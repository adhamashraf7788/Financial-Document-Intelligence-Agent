import os
from dotenv import load_dotenv

load_dotenv()

# Single source of truth: base URL only. Paths are appended per-call in api_client.py,
# so setting this once behaves consistently for both dashboard and query calls
# (previously process_query and load_dashboard_data defaulted this differently — issue #2).
ORCHESTRATOR_BASE_URL = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://localhost:8000").rstrip("/")

ORCHESTRATOR_DASHBOARD_PATH = "/api/v1/dashboard"
# NOTE: no orchestrator-service exists yet, so this currently points straight
# at agent-service's real path. Once orchestrator-service exists and proxies
# /api/v1/query -> agent-service, switch this back to "/api/v1/query" and
# repoint ORCHESTRATOR_SERVICE_URL at the orchestrator instead.
ORCHESTRATOR_QUERY_PATH = "/api/v1/agent/query"

REQUEST_TIMEOUT_QUERY = float(os.getenv("UI_QUERY_TIMEOUT", "15.0"))
REQUEST_TIMEOUT_DASHBOARD = float(os.getenv("UI_DASHBOARD_TIMEOUT", "3.0"))

GRADIO_SHARE = os.getenv("GRADIO_SHARE", "False").lower() == "true"

MOCK_UI_PATH = os.getenv(
    "MOCK_UI_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../mock-data/ui_service_mock.json")),
)