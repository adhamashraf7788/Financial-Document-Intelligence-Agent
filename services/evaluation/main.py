from pathlib import Path

from fastapi import FastAPI
from dotenv import load_dotenv
from langfuse import get_client
from pydantic import BaseModel

from services.evaluation.harness import run_benchmark
from services.evaluation.predictor import predict_answer
from services.evaluation.experiments import run_pipeline_experiment

load_dotenv(Path(__file__).resolve().parent / ".env")

langfuse = get_client()

app = FastAPI(title="Evaluation & Observability Service")

DEFAULT_QUESTIONS_PATH = "mock-data/eval_questions/questions_setA_practice.json"


class BenchmarkRequest(BaseModel):
    questions_path: str = DEFAULT_QUESTIONS_PATH


class ExperimentRequest(BaseModel):
    experiment_name: str = "pipeline_variant_comparison"
    questions_path: str = DEFAULT_QUESTIONS_PATH
    sample_size: int | None = None


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "eval-service"}


@app.post("/evaluate")
def evaluate(request: BenchmarkRequest = BenchmarkRequest()):
    report = run_benchmark(request.questions_path)
    return report


@app.post("/evaluate/experiment")
def evaluate_experiment(request: ExperimentRequest = ExperimentRequest()):
    report = run_pipeline_experiment(
        questions_path=request.questions_path,
        baseline_fn=predict_answer,
        variant_fn=predict_answer,
        experiment_name=request.experiment_name,
        sample_size=request.sample_size,
    )
    return report