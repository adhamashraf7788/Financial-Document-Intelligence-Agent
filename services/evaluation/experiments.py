from typing import Callable, Dict, Any, Optional
from langfuse import observe

from services.evaluation.harness import run_benchmark


def compute_metric_deltas(baseline: Dict[str, Any], variant: Dict[str, Any]) -> Dict[str, Any]:
    deltas = {}
    metric_keys = [
        "exact_match",
        "f1",
        "numerical_accuracy",
        "correct_refusal_rate",
        "recall_at_k",
        "precision_at_k",
        "mrr",
    ]

    for key in metric_keys:
        b_val = baseline.get(key)
        v_val = variant.get(key)
        if b_val is not None and v_val is not None:
            diff = round(v_val - b_val, 4)
            pct = round((diff / b_val) * 100, 2) if b_val != 0 else (0.0 if diff == 0 else None)
            deltas[key] = {
                "baseline": b_val,
                "variant": v_val,
                "diff": diff,
                "pct_change": pct,
                "improved": diff > 0,
            }
        else:
            deltas[key] = None

    b_lat = baseline.get("system_performance", {}).get("avg_latency_ms_per_question")
    v_lat = variant.get("system_performance", {}).get("avg_latency_ms_per_question")
    if b_lat is not None and v_lat is not None:
        diff = round(v_lat - b_lat, 2)
        deltas["latency_ms"] = {
            "baseline": b_lat,
            "variant": v_lat,
            "diff": diff,
            "improved": diff < 0,
        }
    else:
        deltas["latency_ms"] = None

    return deltas


def generate_experiment_conclusion(deltas: Dict[str, Any]) -> str:
    improvements = 0
    regressions = 0

    for key, data in deltas.items():
        if data and isinstance(data, dict) and "improved" in data:
            if data["diff"] != 0:
                if data["improved"]:
                    improvements += 1
                else:
                    regressions += 1

    if improvements > regressions:
        return (
            f"Variant improved performance across {improvements} metric(s) "
            f"(with {regressions} regression(s)). Measurable positive impact."
        )
    elif regressions > improvements:
        return (
            f"Variant degraded performance across {regressions} metric(s) "
            f"(with {improvements} improvement(s)). Measurable negative impact."
        )
    else:
        return "Variant showed neutral or identical performance compared to baseline."


@observe()
def run_pipeline_experiment(
    questions_path: str,
    baseline_fn: Callable,
    variant_fn: Callable,
    experiment_name: str = "pipeline_variant_comparison",
    sample_size: Optional[int] = None,
) -> Dict[str, Any]:
    baseline_report = run_benchmark(questions_path, predict_fn=baseline_fn, sample_size=sample_size)
    variant_report = run_benchmark(questions_path, predict_fn=variant_fn, sample_size=sample_size)

    deltas = compute_metric_deltas(baseline_report, variant_report)
    conclusion = generate_experiment_conclusion(deltas)

    return {
        "experiment_name": experiment_name,
        "sample_size": baseline_report.get("total_questions", 0),
        "baseline": baseline_report,
        "variant": variant_report,
        "deltas": deltas,
        "conclusion": conclusion,
    }
