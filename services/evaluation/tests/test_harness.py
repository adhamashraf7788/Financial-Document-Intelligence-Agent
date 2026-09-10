import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_benchmark
from shared.schemas import InsufficientEvidenceAnswer

QUESTIONS_PATH = str(
    Path(__file__).resolve().parent.parent.parent.parent
    / "mock-data" / "eval_questions" / "questions_setA_practice.json"
)

def _mock_predict(question: str, document_id=None):
    answer = InsufficientEvidenceAnswer(
        answer_type="insufficient_evidence",
        evidence=[],
        params={"reason": "mock predictor"},
    )
    return answer, None


def test_run_benchmark_produces_full_report_shape():
    report = run_benchmark(QUESTIONS_PATH, predict_fn=_mock_predict)

    assert report["total_questions"] == 100
    assert "exact_match" in report
    assert "f1" in report
    assert "numerical_accuracy" in report
    assert "correct_refusal_rate" in report
    assert "recall_at_k" in report
    assert "precision_at_k" in report
    assert "mrr" in report


def test_run_benchmark_metrics_are_valid_ranges():
    report = run_benchmark(QUESTIONS_PATH, predict_fn=_mock_predict)

    for key in ("exact_match", "f1", "numerical_accuracy", "correct_refusal_rate",
                "recall_at_k", "precision_at_k", "mrr"):
        value = report[key]
        assert value is None or 0.0 <= value <= 1.0