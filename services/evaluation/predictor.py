import random
from models import DirectAnswer, CalculatedAnswer, MultiSpanAnswer, InsufficientEvidenceAnswer, Evidence, Answer


def predict_answer(question: str) -> Answer:

    # Stub predictor. Returns a randomly-shaped, valid Answer.
    
    choice = random.choice(["direct", "calculated", "multi_span", "insufficient_evidence"])

    dummy_evidence = [Evidence(document_id="doc_000", page=1, section="Mock Section")]

    if choice == "direct":
        return DirectAnswer(
            answer_type="direct",
            evidence=dummy_evidence,
            params={"value": "123"}
        )
    elif choice == "calculated":
        return CalculatedAnswer(
            answer_type="calculated",
            evidence=dummy_evidence,
            params={"value": 42.0, "formula": "(50-8)/8*100"}
        )
    elif choice == "multi_span":
        return MultiSpanAnswer(
            answer_type="multi_span",
            evidence=dummy_evidence,
            params={"values": ["Item A", "Item B"]}
        )
    else:
        return InsufficientEvidenceAnswer(
            answer_type="insufficient_evidence",
            evidence=[],
            params={"reason": "Mock: no evidence found."}
        )