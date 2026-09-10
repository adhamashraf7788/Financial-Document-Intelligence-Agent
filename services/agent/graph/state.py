from typing import List, Optional, Dict, Any, TypedDict


class AgentState(TypedDict):
    question: str
    document_id: Optional[str]
    retrieved_data: List[Dict[str, Any]]
    final_output: Optional[Dict[str, Any]]
    retry_count: int
