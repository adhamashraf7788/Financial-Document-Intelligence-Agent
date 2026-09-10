import os
from dotenv import load_dotenv

load_dotenv()

# Agent service configuration (direct connection, no orchestrator)
AGENT_BASE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:7000").rstrip("/")
AGENT_QUERY_PATH = "/api/v1/agent/query"
AGENT_DASHBOARD_PATH = "/api/v1/dashboard"

REQUEST_TIMEOUT_QUERY = float(os.getenv("UI_QUERY_TIMEOUT", "15.0"))
REQUEST_TIMEOUT_DASHBOARD = float(os.getenv("UI_DASHBOARD_TIMEOUT", "3.0"))

GRADIO_SHARE = os.getenv("GRADIO_SHARE", "False").lower() == "true"

MOCK_UI_PATH = os.getenv(
    "MOCK_UI_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../mock-data/ui_service_mock.json")),
)