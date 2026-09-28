"""Structured human review, deterministic aggregation and quality comparison."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evidenceops.evaluation import Case, Dataset, Run, Text, validate_baseline

type Dimension = Literal["relevance", "factual_correctness", "prudence_and_limitations"]


class RubricCase(Case):
    dimensions: list[Dimension] = Field(min_length=1)
    reference_facts: list[Text] = Field(min_length=1)
    expected_behavior: list[Text] = Field(min_length=1)
    forbidden_claims: list[Text] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_dimensions(self) -> "RubricCase":
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("Duplicate dimensions")
        return self


class RubricDataset(Dataset):
    cases: list[RubricCase] = Field(min_length=1)


class Judgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: Text
    dimension: Dimension
    verdict: Literal["pass", "fail"] | None = None
    notes: str = ""

    @model_validator(mode="after")
    def explain_failure(self) -> "Judgment":
        if self.verdict == "fail" and not self.notes.strip():
            raise ValueError("A fail requires explanatory notes")
        return self


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_version: Literal["1"] = "1"
    evaluator: Literal["human"] = "human"
    reviewer: str = ""
    run_id: UUID
    run_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_version: Text
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    results: list[Judgment]


def run_digest(run: Run) -> str:
    # Formatting/object-key order do not invalidate a review; content changes do.
    canonical = json.dumps(run.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare_review(run: Run, dataset_path: Path) -> Review:
    validate_baseline(run, dataset_path)
    dataset = RubricDataset.model_validate_json(dataset_path.read_bytes())
    return Review(
        run_id=run.run_id, run_sha256=run_digest(run),
        dataset_version=run.dataset_version, dataset_sha256=run.dataset_sha256,
        results=[Judgment(case_id=case.id, dimension=dimension)
                 for case in dataset.cases for dimension in case.dimensions],
    )


def validate_review(review: Review, run: Run, dataset_path: Path) -> None:
    expected = prepare_review(run, dataset_path)
    if (review.run_id, review.run_sha256, review.dataset_version, review.dataset_sha256) != (
        expected.run_id, expected.run_sha256, expected.dataset_version, expected.dataset_sha256
    ):
        raise ValueError("Review does not match this run/dataset; prepare and review again")
    keys = [(item.case_id, item.dimension) for item in review.results]
    expected_keys = {(item.case_id, item.dimension) for item in expected.results}
    if len(keys) != len(set(keys)) or set(keys) != expected_keys:
        raise ValueError("Review requires exactly the declared case_id + dimension pairs")
    if not review.reviewer.strip() or any(item.verdict is None for item in review.results):
        raise ValueError("Incomplete review: reviewer and every verdict are required")
    if any(item.verdict == "fail" and not item.notes.strip() for item in review.results):
        raise ValueError("A fail requires explanatory notes")


def ordered_results(review: Review) -> list[Judgment]:
    return sorted(review.results, key=lambda item: (item.case_id, item.dimension))


def aggregate(review: Review, run: Run, dataset_path: Path) -> dict:
    validate_review(review, run, dataset_path)
    results = ordered_results(review)
    by_dimension = {}
    for dimension in sorted({item.dimension for item in results}):
        by_dimension[dimension] = {
            verdict: sum(item.dimension == dimension and item.verdict == verdict for item in results)
            for verdict in ("pass", "fail")
        }
    failed_cases = {item.case_id for item in results if item.verdict == "fail"}
    passed_cases = sorted({item.case_id for item in results} - failed_cases)
    return {
        "run_id": str(run.run_id), "reviewer": review.reviewer,
        "counts": {verdict: sum(item.verdict == verdict for item in results)
                   for verdict in ("pass", "fail")},
        "by_dimension": by_dimension,
        "fully_passed_cases": passed_cases, "fully_passed_case_count": len(passed_cases),
        "failures": [item.model_dump() for item in results if item.verdict == "fail"],
        "results": [item.model_dump() for item in results],
    }


def compare(
    baseline: Review, baseline_run: Run, candidate: Review, candidate_run: Run,
    dataset_path: Path,
) -> dict:
    # Both must pass against the same exact dataset, including rubric and dimensions.
    validate_review(baseline, baseline_run, dataset_path)
    validate_review(candidate, candidate_run, dataset_path)
    previous = {(item.case_id, item.dimension): item for item in baseline.results}
    transitions = {
        ("pass", "pass"): "unchanged_pass", ("fail", "fail"): "unchanged_fail",
        ("fail", "pass"): "improvements", ("pass", "fail"): "regressions",
    }
    groups = {name: [] for name in transitions.values()}
    for item in ordered_results(candidate):
        before = previous[item.case_id, item.dimension]
        groups[transitions[before.verdict, item.verdict]].append({
            "case_id": item.case_id, "dimension": item.dimension,
            "baseline": before.verdict, "candidate": item.verdict,
            "baseline_notes": before.notes, "candidate_notes": item.notes,
        })
    return {
        "baseline_run_id": str(baseline_run.run_id),
        "candidate_run_id": str(candidate_run.run_id),
        "counts": {name: len(items) for name, items in groups.items()}, **groups,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Create an unfilled review JSON")
    prepare.add_argument("run", type=Path)
    prepare.add_argument("destination", type=Path)
    summary = commands.add_parser("aggregate", help="Validate and summarize a complete review")
    summary.add_argument("run", type=Path)
    summary.add_argument("review", type=Path)
    comparison = commands.add_parser("compare", help="Compare complete reviews; exit 1 on regression")
    comparison.add_argument("baseline_run", type=Path)
    comparison.add_argument("baseline_review", type=Path)
    comparison.add_argument("candidate_run", type=Path)
    comparison.add_argument("candidate_review", type=Path)
    for command in (prepare, summary, comparison):
        command.add_argument("--dataset", type=Path, default=Path("evaluation/cases.json"))
    args = parser.parse_args(argv)

    def load_run(path: Path) -> Run:
        return Run.model_validate_json(path.read_bytes())

    def load_review(path: Path) -> Review:
        return Review.model_validate_json(path.read_bytes())

    try:
        if args.command == "prepare":
            review = prepare_review(load_run(args.run), args.dataset)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            with args.destination.open("x", encoding="utf-8") as stream:
                stream.write(review.model_dump_json(indent=2) + "\n")
            print(args.destination)
            return 0
        if args.command == "aggregate":
            report = aggregate(load_review(args.review), load_run(args.run), args.dataset)
        else:
            report = compare(
                load_review(args.baseline_review), load_run(args.baseline_run),
                load_review(args.candidate_review), load_run(args.candidate_run), args.dataset,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return int(args.command == "compare" and bool(report["regressions"]))
    except (ValueError, OSError):
        # Pydantic errors can echo full input; do not print response bodies.
        parser.exit(2, "Invalid review/run/dataset or file access: check completeness, "
                    "fail notes, reviewer, matching hashes and unique declared pairs.\n")


if __name__ == "__main__":
    raise SystemExit(main())
