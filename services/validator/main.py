from fastapi import FastAPI

from services.validator.validation import validate_answer
from services.validator.models import ValidationResponse

app = FastAPI(title="Answer Validator Service")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "answer-validator-api"}


@app.post("/validate_answer", response_model=ValidationResponse)
async def validate_answer_endpoint(payload: dict) -> ValidationResponse:
    return validate_answer(payload)