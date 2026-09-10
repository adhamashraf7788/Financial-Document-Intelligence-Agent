from pydantic import ValidationError
from shared.schemas import ANSWER_TYPE_MAP
from services.validator.models import ValidationResponse
import re

def is_close(a: float, b: float, rel_tolerance: float = 0.001, abs_tolerance: float = 1e-6) -> bool:
    return abs(a - b) <= max(rel_tolerance * max(abs(a), abs(b)), abs_tolerance)

def is_safe_arithmetic(formula: str) -> bool:
    return bool(re.fullmatch(r"[0-9+\-*/().\s]+", formula))

def evaluate_formula(formula: str) -> float:
    if not is_safe_arithmetic(formula):
        raise ValueError(f"Unsafe characters in formula: {formula!r}")
    return eval(formula, {"__builtins__": {}}, {})

def validate_answer(payload: dict) -> ValidationResponse:
    answer_type = payload.get("answer_type")

    if answer_type not in ANSWER_TYPE_MAP:
        message = f"Invalid answer. Reason: Unknown answer_type '{answer_type}'."
        print(f"[ANSWER-VALIDATOR-ERROR] {message}")
        return ValidationResponse(valid=False, message=message)

    schema_class = ANSWER_TYPE_MAP[answer_type]

    try:
        answer = schema_class(**payload)
    except ValidationError as e:
        reason = str(e.errors()[0]["msg"])
        message = f"Invalid answer for '{answer_type}': {reason}"
        print(f"[ANSWER-VALIDATOR-ERROR] {message}")
        return ValidationResponse(valid=False, message=message)

    if answer_type == "calculated":
        try:
            computed = evaluate_formula(answer.params.formula)
        except ValueError as e:
            message = f"Invalid answer for 'calculated': {e}"
            print(f"[ANSWER-VALIDATOR-ERROR] {message}")
            return ValidationResponse(valid=False, message=message)

        if not is_close(computed, answer.params.value):
            message = (
                f"Invalid answer for 'calculated': formula '{answer.params.formula}' "
                f"evaluates to {computed}, but reported value was {answer.params.value}."
            )
            print(f"[ANSWER-VALIDATOR-ERROR] {message}")
            return ValidationResponse(valid=False, message=message)

    evidence_summary = answer.evidence[0].model_dump() if answer.evidence else {}
    message = f"Received and validated answer of type '{answer_type}' with evidence {evidence_summary}"
    print(f"[ANSWER-VALIDATOR-SUCCESS] {message}")
    return ValidationResponse(valid=True, message=message)