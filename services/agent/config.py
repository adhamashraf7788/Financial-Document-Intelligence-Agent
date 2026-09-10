import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# --- Retrieval / HTTP ---
RETRIEVAL_SERVICE_URL = os.getenv(
    "RETRIEVAL_SERVICE_URL", "http://localhost:8001/api/v1/search/pipeline"
)
HTTP_TIMEOUT = float(os.getenv("RETRIEVAL_HTTP_TIMEOUT", "8.0"))

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-20b")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "20.0"))  # bounds the LLM call itself

llm = (
    ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=LLM_MODEL_NAME,
        temperature=0,
        timeout=LLM_TIMEOUT,
    )
    if GROQ_API_KEY
    else None
)

# --- Retry policy ---
MAX_RETRIEVAL_RETRIES = int(os.getenv("MAX_RETRIEVAL_RETRIES", "1"))
MAX_LLM_ATTEMPTS = int(os.getenv("MAX_LLM_ATTEMPTS", "2"))  # 1 initial + 1 retry