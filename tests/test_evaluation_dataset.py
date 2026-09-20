import json
from pathlib import Path


def test_evaluation_dataset_structure() -> None:
    """Protect the versioned artifact, not the quality of generated answers."""
    path = Path(__file__).resolve().parents[1] / "evaluation" / "cases.json"
    dataset = json.loads(path.read_text(encoding="utf-8"))

    assert set(dataset) == {"dataset_version", "description", "cases"}
    assert dataset["dataset_version"] == "0.1"
    assert isinstance(dataset["description"], str) and dataset["description"].strip()
    cases = dataset["cases"]
    assert isinstance(cases, list) and len(cases) == 10

    dimensions = {"relevance", "factual_correctness", "prudence_and_limitations"}
    text_fields = {"id", "question", "category", "notes"}
    list_fields = {
        "dimensions", "reference_facts", "expected_behavior", "forbidden_claims"
    }
    ids = set()
    for case in cases:
        assert isinstance(case, dict)
        assert set(case) == text_fields | list_fields
        for field in text_fields:
            assert isinstance(case[field], str) and case[field].strip(), field
        assert case["id"] not in ids, case["id"]
        ids.add(case["id"])
        for field in list_fields:
            values = case[field]
            assert isinstance(values, list) and values, (case["id"], field)
            assert all(isinstance(value, str) and value.strip() for value in values)
        assert set(case["dimensions"]) <= dimensions, case["id"]
        assert len(case["dimensions"]) == len(set(case["dimensions"]))
