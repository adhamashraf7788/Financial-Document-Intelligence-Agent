from typing import Callable
from services.evaluation.loader import load_questions
from services.evaluation.predictor import predict_answer
from services.evaluation.scorer import exact_match, f1_score, numerical_accuracy, retrieval_recall_at_k, retrieval_precision_at_k, reciprocal_rank
from langfuse import observe
from pathlib import Path
from dotenv import load_dotenv
import time

load_dotenv(Path(__file__).resolve().parent / ".env")

def extract_predicted_value(answer):

    if answer.answer_type == "insufficient_evidence":
        return None
    if answer.answer_type == "multi_span":
        return answer.params.values
    return answer.params.value

def score_retrieval(question: dict, retrieval_results: list[dict] | None, k: int = 5) -> dict:
    #based on the retrieval readme
    if retrieval_results is None:
        return {}

    gold_doc_ids = [ev["source_doc_uid"] for ev in question.get("gold_evidence", [])]
    retrieved_doc_ids = [r["metadata"]["document_id"] for r in retrieval_results]

    return {
        "recall_at_k": retrieval_recall_at_k(gold_doc_ids, retrieved_doc_ids, k=k),
        "precision_at_k": retrieval_precision_at_k(gold_doc_ids, retrieved_doc_ids, k=k),
        "reciprocal_rank": reciprocal_rank(gold_doc_ids, retrieved_doc_ids),
    }

@observe()
def score_question(question: dict, predicted_answer, retrieval_results: list[dict] | None = None) -> dict:

    gt_type = question["answer_type"]
    ground_truth = question["ground_truth_answer"]
    predicted_value = extract_predicted_value(predicted_answer)

    result = {"question_id": question["question_id"], "gt_type": gt_type}

    if gt_type == "unanswerable":
        result["correct_refusal"] = int(predicted_answer.answer_type == "insufficient_evidence")

    elif predicted_value is None:
        # predictor refused, but this question actually had an answer
        result["em"] = 0
        result["f1"] = 0.0
        if gt_type in ("arithmetic", "count"):
            result["numerical_accuracy"] = 0

    elif gt_type in ("arithmetic", "count"):
        result["numerical_accuracy"] = numerical_accuracy(
            predicted_value, ground_truth, scale=question.get("scale")
        )

    else:
        def to_text(value):
            if isinstance(value, str):
                return value
            if isinstance(value, (list, tuple)):
                return " ".join(map(str, value))
            return str(value)

        gt_text = to_text(ground_truth)
        pred_text = to_text(predicted_value)

        result["em"] = exact_match(pred_text, gt_text)
        result["f1"] = f1_score(pred_text, gt_text)

    result.update(score_retrieval(question, retrieval_results=retrieval_results))
    return result

@observe()
def run_benchmark(
    questions_path: str,
    predict_fn: Callable = predict_answer,
    sample_size: int | None = None,
) -> dict:

    questions = load_questions(questions_path)
    if sample_size is not None and sample_size > 0:
        questions = questions[:sample_size]

    start = time.perf_counter()
    results = []
    for q in questions:
        answer, retrieval_results = predict_fn(q["question_text"])
        results.append(score_question(q, answer, retrieval_results))
    total_time = time.perf_counter() - start

    ems = [r["em"] for r in results if "em" in r]
    f1s = [r["f1"] for r in results if "f1" in r]
    num_accs = [r["numerical_accuracy"] for r in results if "numerical_accuracy" in r]
    refusals = [r["correct_refusal"] for r in results if "correct_refusal" in r]
    recalls = [r["recall_at_k"] for r in results if "recall_at_k" in r]
    precisions = [r["precision_at_k"] for r in results if "precision_at_k" in r]
    rrs = [r["reciprocal_rank"] for r in results if "reciprocal_rank" in r]

    report = {
        "total_questions": len(questions),
        "exact_match": sum(ems) / len(ems) if ems else None,
        "f1": sum(f1s) / len(f1s) if f1s else None,
        "numerical_accuracy": sum(num_accs) / len(num_accs) if num_accs else None,
        "correct_refusal_rate": sum(refusals) / len(refusals) if refusals else None,
        "recall_at_k": sum(recalls) / len(recalls) if recalls else None,
        "precision_at_k": sum(precisions) / len(precisions) if precisions else None,
        "mrr": sum(rrs) / len(rrs) if rrs else None,
        "system_performance": {
            "total_time_seconds": round(total_time, 4),
            "avg_latency_ms_per_question": round((total_time / len(questions)) * 1000, 2) if questions else None,
            "llm_calls_per_query": 0,
            "avg_token_usage": None,
            "approximate_cost_usd": 0.0,
        },
    }
    return report