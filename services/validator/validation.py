from pydantic import ValidationError
from shared.schemas import ANSWER_TYPE_MAP
from services.validator.models import ValidationResponse


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

    evidence_summary = answer.evidence[0].model_dump() if answer.evidence else {}
    message = f"Received and validated answer of type '{answer_type}' with evidence {evidence_summary}"
    print(f"[ANSWER-VALIDATOR-SUCCESS] {message}")
    return ValidationResponse(valid=True, message=message)