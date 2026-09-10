from typing import Tuple
from pydantic import TypeAdapter, ValidationError

from schemas import StructuredAgentOutput

_adapter = TypeAdapter(StructuredAgentOutput)


def validate_answer(parsed: dict) -> Tuple[bool, str]:
    """Validates parsed LLM output against the Strict Answer Schema
    (direct / calculated / multi_span / insufficient_evidence).

    Returns (is_valid, error_message). On success, error_message is "".
    """
    try:
        _adapter.validate_python(parsed)
        return True, ""
    except ValidationError as e:
        return False, str(e)
