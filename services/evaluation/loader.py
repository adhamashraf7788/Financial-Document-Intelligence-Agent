import json
from pathlib import Path
from langfuse import observe

@observe()

def load_questions(path: str) -> list[dict]:

    #loads the practice question set and returns a simplified list of dicts with just the fields the scorers need

    file_path = Path(path)
    with open(file_path, "r", encoding="utf-8") as f:
        raw_questions = json.load(f)

    loaded = []
    for q in raw_questions:
        loaded.append({
            "question_id": q["question_id"],
            "question_text": q["question_text"],
            "ground_truth_answer": q["ground_truth_answer"],
            "answer_type": q["answer_type"],
            "scale": q.get("scale"),
            "is_answerable": q["is_answerable"],
            "gold_evidence": q.get("gold_evidence", []),
        })

    return loaded