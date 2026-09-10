from app import format_citations, process_query


def test_format_citations_with_data():
    evidence = [{"document_id": "doc_017", "page": 1, "section": "Notes"}]
    result = format_citations(evidence)
    assert "doc_017" in result
    assert "Page:" in result


def test_format_citations_empty():
    result = format_citations([])
    assert "No citations provided" in result


def test_process_query_fallback_calculated():
    formatted_res, answer_type, json_res = process_query("calculate 5 + 5", "")
    assert answer_type == "calculated"
    assert "formula" in json_res


def test_process_query_empty_input():
    formatted_res, answer_type, json_res = process_query("", "")
    assert formatted_res == "Please enter a valid question."
    assert answer_type == "N/A"