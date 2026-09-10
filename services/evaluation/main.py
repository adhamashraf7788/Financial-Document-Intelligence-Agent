from pathlib import Path

from fastapi import FastAPI
from dotenv import load_dotenv
from langfuse import get_client
from pydantic import BaseModel

from services.evaluation.harness import run_benchmark

load_dotenv(Path(__file__).resolve().parent / ".env")

langfuse = get_client()

app = FastAPI(title="Evaluation & Observability Service")

DEFAULT_QUESTIONS_PATH = "mock-data/eval_questions/questions_setA_practice.json"


class BenchmarkRequest(BaseModel):

    questions_path: str = DEFAULT_QUESTIONS_PATH

@app.get("/ping")
def ping():
    
    return {"status": "ok"}

@app.post("/evaluate")
def evaluate(request: BenchmarkRequest = BenchmarkRequest()):

    report = run_benchmark(request.questions_path)

    return report