import sys
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments import (
    compute_metric_deltas,
    generate_experiment_conclusion,
    run_pipeline_experiment,
)
from shared.schemas import InsufficientEvidenceAnswer, DirectAnswer, Evidence
from services.evaluation.main import app

QUESTIONS_PATH = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "mock-data" / "eval_questions" / "questions_setA_practice.json"
)


def test_compute_metric_deltas_improvement():
    baseline = {
        "exact_match": 0.40,
        "f1": 0.50,
        "numerical_accuracy": 0.30,
        "correct_refusal_rate": 0.80,
        "recall_at_k": 0.60,
        "precision_at_k": 0.50,
        "mrr": 0.55,
        "system_performance": {"avg_latency_ms_per_question": 120.0},
    }
    variant = {
        "exact_match": 0.60,
        "f1": 0.70,
        "numerical_accuracy": 0.45,
        "correct_refusal_rate": 0.85,
        "recall_at_k": 0.75,
        "precision_at_k": 0.65,
        "mrr": 0.70,
        "system_performance": {"avg_latency_ms_per_question": 95.0},
    }

    deltas = compute_metric_deltas(baseline, variant)

    assert deltas["exact_match"]["diff"] == 0.20
    assert deltas["exact_match"]["improved"] is True
    assert deltas["f1"]["diff"] == 0.20
    assert deltas["f1"]["improved"] is True
    assert deltas["recall_at_k"]["diff"] == 0.15
    assert deltas["recall_at_k"]["improved"] is True
    assert deltas["latency_ms"]["diff"] == -25.0
    assert deltas["latency_ms"]["improved"] is True


def test_compute_metric_deltas_regression():
    baseline = {
        "exact_match": 0.50,
        "f1": 0.60,
        "recall_at_k": 0.70,
        "system_performance": {"avg_latency_ms_per_question": 100.0},
    }
    variant = {
        "exact_match": 0.30,
        "f1": 0.40,
        "recall_at_k": 0.50,
        "system_performance": {"avg_latency_ms_per_question": 150.0},
    }

    deltas = compute_metric_deltas(baseline, variant)

    assert deltas["exact_match"]["diff"] == -0.20
    assert deltas["exact_match"]["improved"] is False
    assert deltas["latency_ms"]["diff"] == 50.0
    assert deltas["latency_ms"]["improved"] is False


def test_generate_experiment_conclusion():
    improved_deltas = {
        "exact_match": {"diff": 0.1, "improved": True},
        "f1": {"diff": 0.1, "improved": True},
        "latency_ms": {"diff": -10, "improved": True},
    }
    conclusion = generate_experiment_conclusion(improved_deltas)
    assert "positive impact" in conclusion.lower()

    degraded_deltas = {
        "exact_match": {"diff": -0.1, "improved": False},
        "f1": {"diff": -0.1, "improved": False},
    }
    conclusion = generate_experiment_conclusion(degraded_deltas)
    assert "negative impact" in conclusion.lower()

    neutral_deltas = {
        "exact_match": {"diff": 0.0, "improved": False},
    }
    conclusion = generate_experiment_conclusion(neutral_deltas)
    assert "neutral" in conclusion.lower()


def test_run_pipeline_experiment_offline():
    def mock_baseline(q):
        return (
            InsufficientEvidenceAnswer(
                answer_type="insufficient_evidence",
                evidence=[],
                params={"reason": "baseline mock"},
            ),
            None,
        )

    def mock_variant(q):
        return (
            DirectAnswer(
                answer_type="direct",
                evidence=[Evidence(document_id="doc_017", page=1, section="Income Statement")],
                params={"value": "mock value"},
            ),
            [{"metadata": {"document_id": "doc_017"}}],
        )

    experiment_report = run_pipeline_experiment(
        questions_path=QUESTIONS_PATH,
        baseline_fn=mock_baseline,
        variant_fn=mock_variant,
        experiment_name="test_offline_ablation",
        sample_size=5,
    )

    assert experiment_report["experiment_name"] == "test_offline_ablation"
    assert experiment_report["sample_size"] == 5
    assert "baseline" in experiment_report
    assert "variant" in experiment_report
    assert "deltas" in experiment_report
    assert "conclusion" in experiment_report
    assert experiment_report["baseline"]["total_questions"] == 5
    assert experiment_report["variant"]["total_questions"] == 5


def test_eval_service_endpoints():
    client = TestClient(app)

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok", "service": "eval-service"}

    ping_resp = client.get("/ping")
    assert ping_resp.status_code == 200
    assert ping_resp.json() == {"status": "ok"}

