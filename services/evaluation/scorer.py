import re

def exact_match(predicted, ground_truth) -> int:

    def normalize(value):
        return str(value).strip().lower()

    return int(normalize(predicted) == normalize(ground_truth))


def f1_score(predicted, ground_truth) -> float: #partial match

    def tokenize(value):
        return str(value).strip().lower().split()

    pred_tokens = tokenize(predicted)
    truth_tokens = tokenize(ground_truth)

    if len(pred_tokens) == 0 or len(truth_tokens) == 0:
        return int(pred_tokens == truth_tokens)

    common = set(pred_tokens) & set(truth_tokens)
    num_common = len(common)

    if num_common == 0:
        return 0.0

    precision = num_common / len(pred_tokens)
    recall = num_common / len(truth_tokens)

    return 2 * (precision * recall) / (precision + recall) #harmonic mean


SCALE_MULTIPLIERS = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "percent": 1,
    None: 1,
}

SCALE_WORD_MAP = {
    "thousand": "thousand", "thousands": "thousand", "k": "thousand",
    "million": "million", "millions": "million", "mn": "million", "mm": "million", "m": "million",
    "billion": "billion", "billions": "billion", "bn": "billion", "b": "billion",
    "percent": "percent", "%": "percent", "pct": "percent",
}


def parse_scaled_number(value):

    if isinstance(value, (int, float)):
        return float(value), None

    text = str(value).strip().replace(",", "").replace("$", "")
    text = re.sub(r"per\s*cent", "percent", text, flags=re.IGNORECASE)

    is_negative_paren = False
    if text.startswith("(") and ")" in text:
        close_idx = text.index(")")
        inner = text[1:close_idx]
        suffix_after = text[close_idx + 1:]
        text = inner + suffix_after
        is_negative_paren = True

    match = re.search(r"([-+]?\d*\.?\d+)\s*([a-zA-Z%]+)?", text)
    if not match:
        raise ValueError(f"Could not parse a number from: {value!r}")

    numeric_value = float(match.group(1))
    if is_negative_paren:
        numeric_value = -abs(numeric_value)

    suffix = (match.group(2) or "").strip().lower()
    detected_scale = SCALE_WORD_MAP.get(suffix)

    return numeric_value, detected_scale


def numerical_accuracy(predicted, ground_truth, scale=None, tolerance=0.01) -> int:

    try:
        truth_number, _ = parse_scaled_number(ground_truth)
        pred_number, pred_scale = parse_scaled_number(predicted)
    except ValueError:
        return 0

    truth_multiplier = SCALE_MULTIPLIERS.get(scale, 1)
    truth_real = truth_number * truth_multiplier

    if pred_scale is not None:
        pred_multiplier = SCALE_MULTIPLIERS.get(pred_scale, 1)
    else:
        pred_multiplier = truth_multiplier

    pred_real = pred_number * pred_multiplier

    if truth_real == 0:
        return int(abs(pred_real) < tolerance)

    relative_diff = abs(pred_real - truth_real) / abs(truth_real)
    return int(relative_diff <= tolerance)

def retrieval_recall_at_k(gold_doc_ids: list[str], retrieved_doc_ids: list[str], k: int = 5) -> float:
    if not gold_doc_ids:
        return 1.0

    top_k = set(retrieved_doc_ids[:k])
    gold_set = set(gold_doc_ids)
    found = gold_set & top_k

    return len(found) / len(gold_set)

def retrieval_precision_at_k(gold_doc_ids: list[str], retrieved_doc_ids: list[str], k: int = 5) -> float:
    top_k = retrieved_doc_ids[:k]
    if not top_k:
        return 0.0

    gold_set = set(gold_doc_ids)
    correct = sum(1 for doc_id in top_k if doc_id in gold_set)

    return correct / len(top_k)

def reciprocal_rank(gold_doc_ids: list[str], retrieved_doc_ids: list[str]) -> float:
    gold_set = set(gold_doc_ids)

    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in gold_set:
            return 1.0 / rank

    return 0.0