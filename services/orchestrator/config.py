import os


class Settings:
    AGENT_URL = os.getenv("AGENT_URL", "http://agent:8000")
    RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://retrieval:8000")
    RERANKER_URL = os.getenv("RERANKER_URL", "http://reranker:8000")
    DOC_PROCESSOR_URL = os.getenv(
        "DOC_PROCESSOR_URL",
        "http://doc_processor:8000"
    )
    VALIDATOR_URL = os.getenv(
        "VALIDATOR_URL",
        "http://validator:8000"
    )

    ORCHESTRATOR_API_KEY = os.getenv("ORCHESTRATOR_API_KEY")

    REQUEST_TIMEOUT = float(
        os.getenv("ORCHESTRATOR_REQUEST_TIMEOUT", "60")
    )


settings = Settings()