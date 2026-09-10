from loader import load_questions
from predictor import predict_answer
from scorer import exact_match, f1_score, numerical_accuracy


def extract_predicted_value(answer):

    if answer.answer_type == "insufficient_evidence":
        return None
    if answer.answer_type == "multi_span":
        return answer.params.get("values")
    return answer.params.get("value")


def score_question(question: dict, predicted_answer) -> dict:
    
    gt_type = question["answer_type"]
    ground_truth = question["ground_truth_answer"]
    predicted_value = extract_predicted_value(predicted_answer)

    result = {"question_id": question["question_id"], "gt_type": gt_type}

    if gt_type == "unanswerable":
        result["correct_refusal"] = int(predicted_answer.answer_type == "insufficient_evidence")
        return result

    if predicted_value is None:
        # predictor refused, but this question actually had an answer
        result["em"] = 0
        result["f1"] = 0.0
        if gt_type in ("arithmetic", "count"):
            result["numerical_accuracy"] = 0
        return result

    if gt_type in ("arithmetic", "count"):
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

    return result


def run_benchmark(questions_path: str) -> dict:

    questions = load_questions(questions_path)
    results = [score_question(q, predict_answer(q["question_text"])) for q in questions]

    ems = [r["em"] for r in results if "em" in r]
    f1s = [r["f1"] for r in results if "f1" in r]
    num_accs = [r["numerical_accuracy"] for r in results if "numerical_accuracy" in r]
    refusals = [r["correct_refusal"] for r in results if "correct_refusal" in r]

    report = {
        "total_questions": len(questions),
        "exact_match": sum(ems) / len(ems) if ems else None,
        "f1": sum(f1s) / len(f1s) if f1s else None,
        "numerical_accuracy": sum(num_accs) / len(num_accs) if num_accs else None,
        "correct_refusal_rate": sum(refusals) / len(refusals) if refusals else None,
    }
    return report