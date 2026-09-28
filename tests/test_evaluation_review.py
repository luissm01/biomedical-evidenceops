import json
from pathlib import Path
from uuid import uuid4

import pytest

from evidenceops import evaluation, evaluation_review as review
from evidenceops.config import GenerationSettings
from evidenceops.generation import GeneratedContent


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    """Exercise #16 -> review with fake outputs and different declared dimensions."""
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps({
        "dataset_version": "test", "cases": [
            {"id": case_id, "question": f"Question {case_id}", "dimensions": dimensions,
             "reference_facts": ["Reference fact"], "expected_behavior": ["Expected behavior"],
             "forbidden_claims": ["Forbidden meaning"]}
            for case_id, dimensions in [
                ("a", ["relevance", "factual_correctness"]),
                ("b", ["relevance", "prudence_and_limitations"]),
            ]
        ],
    }))
    class Fake:
        def generate(self, question):
            return GeneratedContent(answer=question, limitations=[])

    monkeypatch.setattr(evaluation, "git_state", lambda _: ("a" * 40, False))
    path = evaluation.run_evaluation(
        Fake(), dataset_path=dataset, repo=tmp_path, output_dir=tmp_path / "runs",
        settings=GenerationSettings(_env_file=None, gemini_api_key=None),
    )
    run = evaluation.Run.model_validate_json(path.read_bytes())
    completed = review.prepare_review(run, dataset)
    completed.reviewer = "test human"
    for item in completed.results:
        item.verdict = "pass"
    return dataset, run, completed, path


def test_template_only_declared_dimensions_and_no_default_pass(artifacts):
    dataset, run, _, _ = artifacts
    template = review.prepare_review(run, dataset)
    assert len(template.results) == 4
    assert all(item.verdict is None for item in template.results)
    assert ("b", "factual_correctness") not in {
        (item.case_id, item.dimension) for item in template.results
    }
    with pytest.raises(ValueError, match="Incomplete"):
        review.aggregate(template, run, dataset)


def test_aggregate_keeps_individual_failures_and_is_order_independent(artifacts):
    dataset, run, completed, _ = artifacts
    completed.results[1].verdict = "fail"
    completed.results[1].notes = "Contradicts reference fact"
    report = review.aggregate(completed, run, dataset)
    assert report["counts"] == {"pass": 3, "fail": 1}
    assert report["by_dimension"] == {
        "factual_correctness": {"pass": 0, "fail": 1},
        "prudence_and_limitations": {"pass": 1, "fail": 0},
        "relevance": {"pass": 2, "fail": 0},
    }
    assert report["fully_passed_cases"] == ["b"]
    assert report["fully_passed_case_count"] == 1
    assert report["failures"] == [completed.results[1].model_dump()]
    assert len(report["results"]) == 4
    completed.results.reverse()
    assert review.aggregate(completed, run, dataset) == report


def test_controlled_regression_and_improvement_are_not_cancelled_out(artifacts):
    dataset, baseline_run, baseline, _ = artifacts
    # These are artificial judgments, not automatic assessments of the outputs.
    for index in (2, 3):
        baseline.results[index].verdict = "fail"
        baseline.results[index].notes = "Artificial baseline failure"
    candidate_run = baseline_run.model_copy(deep=True)
    candidate_run.run_id = uuid4()
    candidate_run.model = "different fake model"
    candidate_run.cases[0].output.answer = "Artificially degraded output"
    candidate = review.prepare_review(candidate_run, dataset)
    candidate.reviewer = "test human"
    for index, item in enumerate(candidate.results):
        item.verdict = "fail" if index in (1, 3) else "pass"
        item.notes = "Artificial candidate failure" if item.verdict == "fail" else ""
    report = review.compare(baseline, baseline_run, candidate, candidate_run, dataset)
    assert report["counts"] == {
        "unchanged_pass": 1, "unchanged_fail": 1, "improvements": 1, "regressions": 1,
    }
    assert [(r["case_id"], r["dimension"]) for r in report["regressions"]] == [
        ("a", "factual_correctness")
    ]
    assert [(r["case_id"], r["dimension"]) for r in report["improvements"]] == [
        ("b", "relevance")
    ]
    assert report["regressions"][0]["candidate_notes"] == "Artificial candidate failure"
    assert review.aggregate(baseline, baseline_run, dataset)["counts"] == review.aggregate(
        candidate, candidate_run, dataset
    )["counts"]
    candidate.results.reverse()
    assert review.compare(baseline, baseline_run, candidate, candidate_run, dataset) == report


@pytest.mark.parametrize("change", [
    "missing", "duplicate", "extra_dimension", "unknown_case", "pending", "reviewer",
    "run_id", "run_hash", "dataset_hash", "dataset_version", "empty_fail_notes",
])
def test_invalid_reviews_cannot_aggregate_or_compare(artifacts, change):
    dataset, run, baseline, _ = artifacts
    candidate = baseline.model_copy(deep=True)
    if change == "missing":
        candidate.results.pop()
    elif change == "duplicate":
        candidate.results.append(candidate.results[0])
    elif change == "extra_dimension":
        candidate.results.append(review.Judgment(case_id="b", dimension="factual_correctness", verdict="pass"))
    elif change == "unknown_case":
        candidate.results[0].case_id = "unknown"
    elif change == "pending":
        candidate.results[0].verdict = None
    elif change == "reviewer":
        candidate.reviewer = " "
    elif change == "run_id":
        candidate.run_id = uuid4()
    elif change == "run_hash":
        candidate.run_sha256 = "0" * 64
    elif change == "dataset_hash":
        candidate.dataset_sha256 = "0" * 64
    elif change == "dataset_version":
        candidate.dataset_version = "other"
    else:
        candidate.results[0].verdict = "fail"
        candidate.results[0].notes = " \n"
    with pytest.raises(ValueError):
        review.aggregate(candidate, run, dataset)
    with pytest.raises(ValueError):
        review.compare(baseline, run, candidate, run, dataset)


@pytest.mark.parametrize("change", ["missing", "duplicate", "error", "question", "output", "hash", "version"])
def test_invalid_or_modified_run_rejected(artifacts, change):
    dataset, original, completed, _ = artifacts
    run = original.model_copy(deep=True)
    if change == "missing":
        run.cases.pop()
    elif change == "duplicate":
        run.cases[1] = run.cases[0]
    elif change == "error":
        run.cases[0] = evaluation.Result(case_id="a", question="Question a", status="error", error="rate_limit")
    elif change == "question":
        run.cases[0].question = "changed"
    elif change == "output":
        run.cases[0].output.answer = "changed after review"
    elif change == "hash":
        run.dataset_sha256 = "0" * 64
    else:
        run.dataset_version = "changed"
    with pytest.raises(ValueError):
        review.aggregate(completed, run, dataset)
    with pytest.raises(ValueError):
        review.compare(completed, original, completed, run, dataset)
    if change != "output":
        with pytest.raises(ValueError):
            review.prepare_review(run, dataset)


def test_different_rubric_even_same_version_is_incompatible(artifacts):
    dataset, run, completed, _ = artifacts
    raw = json.loads(dataset.read_text())
    raw["cases"][0]["reference_facts"] = ["Changed rubric"]
    dataset.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        review.compare(completed, run, completed, run, dataset)


@pytest.mark.parametrize("update", [
    {"verdict": "fail"}, {"verdict": "fail", "notes": " \n"},
    {"verdict": "unknown"}, {"verdict": 1}, {"score": 1},
    {"dimension": "groundedness"},
])
def test_judgment_schema_rejects_invalid_values(update):
    raw = {"case_id": "a", "dimension": "relevance", "verdict": "pass", **update}
    with pytest.raises(ValueError):
        review.Judgment.model_validate(raw)


def test_current_dataset_has_28_review_pairs_without_provider():
    dataset = review.RubricDataset.model_validate_json(Path("evaluation/cases.json").read_bytes())
    assert sum(len(case.dimensions) for case in dataset.cases) == 28


def test_cli_workflow_and_exit_codes(artifacts, tmp_path, capsys):
    dataset, run, completed, run_path = artifacts
    destination = tmp_path / "review.json"
    suffix = ["--dataset", str(dataset)]
    assert review.main(["prepare", str(run_path), str(destination), *suffix]) == 0
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        review.main(["prepare", str(run_path), str(destination), *suffix])
    assert exc.value.code == 2  # Does not overwrite human work.
    with pytest.raises(SystemExit) as exc:
        review.main(["aggregate", str(run_path), str(destination), *suffix])
    assert exc.value.code == 2  # Pending judgments are not passes.
    destination.write_text(completed.model_dump_json())
    assert review.main(["aggregate", str(run_path), str(destination), *suffix]) == 0
    assert json.loads(capsys.readouterr().out)["counts"] == {"pass": 4, "fail": 0}
    candidate_path = tmp_path / "candidate-review.json"
    candidate_path.write_text(completed.model_dump_json())
    args = ["compare", str(run_path), str(destination), str(run_path), str(candidate_path), *suffix]
    assert review.main(args) == 0
    capsys.readouterr()
    completed.results[0].verdict = "fail"
    completed.results[0].notes = "Controlled changed judgment"
    candidate_path.write_text(completed.model_dump_json())
    assert review.main(args) == 1
    assert json.loads(capsys.readouterr().out)["counts"]["regressions"] == 1
    candidate_path.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        review.main(args)
    assert exc.value.code == 2
