"""Explicit, sequential evaluation of Generator; no HTTP or database layer."""

import argparse
import hashlib
import subprocess
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from evidenceops.config import GenerationSettings
from evidenceops.generation import (
    GeneratedContent, GenerationError, GenerationErrorCause, Generator,
)

type Text = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]


class Case(BaseModel):
    # Project only inputs/identifiers; never pass the reference rubric to Generator.
    id: Text
    question: Text


class Dataset(BaseModel):
    dataset_version: Text
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self) -> "Dataset":
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate case IDs")
        return self


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: Text
    question: Text
    status: Literal["success", "error"]
    output: GeneratedContent | None = None
    error: GenerationErrorCause | None = None

    @model_validator(mode="after")
    def consistent_status(self) -> "Result":
        valid = (
            self.output is not None and self.error is None
            if self.status == "success"
            else self.output is None and self.error is not None
        )
        if not valid:
            raise ValueError("Inconsistent result")
        return self


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    timestamp_utc: datetime
    dataset_version: Text
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    working_tree_dirty: bool
    model: Text
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    cases: list[Result]


def load_dataset(path: Path) -> tuple[Dataset, str]:
    raw = path.read_bytes()
    return Dataset.model_validate_json(raw), hashlib.sha256(raw).hexdigest()


def git_state(repo: Path) -> tuple[str, bool]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    return git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--untracked-files=all"))


def run_evaluation(
    generator: Generator, *, dataset_path: Path, settings: GenerationSettings,
    repo: Path, output_dir: Path,
) -> Path:
    """Caller owns the generator and supplies its effective configuration."""
    dataset, digest = load_dataset(dataset_path)
    commit, dirty = git_state(repo)
    run = Run(
        run_id=uuid4(), timestamp_utc=datetime.now(UTC),
        dataset_version=dataset.dataset_version, dataset_sha256=digest,
        git_commit=commit, working_tree_dirty=dirty,
        model=settings.gemini_model,
        max_output_tokens=settings.gemini_max_output_tokens,
        timeout_seconds=settings.gemini_timeout_seconds, cases=[],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run.run_id}.json"
    # Reserve before inference; checkpoint atomically after each completed case.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(run.model_dump_json(indent=2) + "\n")
    for case in dataset.cases:
        try:
            output = generator.generate(case.question)
            result = Result(case_id=case.id, question=case.question,
                            status="success", output=output)
        except Exception as exc:
            cause = exc.cause if isinstance(exc, GenerationError) else GenerationErrorCause.UNKNOWN
            result = Result(case_id=case.id, question=case.question,
                            status="error", error=cause)
        run.cases.append(result)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    return path


def validate_baseline(run: Run, dataset_path: Path) -> None:
    dataset, digest = load_dataset(dataset_path)
    if run.dataset_sha256 != digest or run.dataset_version != dataset.dataset_version:
        raise ValueError("Run does not match the dataset")
    expected = [(case.id, case.question) for case in dataset.cases]
    actual = [(case.case_id, case.question) for case in run.cases]
    if actual != expected or any(case.status != "success" for case in run.cases):
        raise ValueError("Baseline requires every dataset case to succeed")


def promote_baseline(source: Path, destination: Path, dataset_path: Path) -> None:
    raw = source.read_bytes()
    validate_baseline(Run.model_validate_json(raw), dataset_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--live", action="store_true", help="Explicitly call Gemini")
    run_parser.add_argument("--output-dir", type=Path, default=Path("evaluation/runs"))
    promote_parser = commands.add_parser("promote")
    promote_parser.add_argument("source", type=Path)
    promote_parser.add_argument("destination", type=Path)
    for command in (run_parser, promote_parser):
        command.add_argument("--dataset", type=Path, default=Path("evaluation/cases.json"))
    args = parser.parse_args(argv)
    if args.command == "run" and not args.live:
        parser.error("run requires --live; this command calls Gemini")
    try:
        if args.command == "promote":
            promote_baseline(args.source, args.destination, args.dataset)
            print(args.destination)
            return 0
        # Validate local prerequisites before constructing the provider client.
        load_dataset(args.dataset)
        git_state(Path.cwd())
        settings = GenerationSettings()
        if settings.gemini_api_key is None:
            parser.error("EVIDENCEOPS_GEMINI_API_KEY is required with --live")
        from evidenceops.gemini import GeminiGenerator

        with closing(GeminiGenerator(
            api_key=settings.gemini_api_key.get_secret_value(),
            model=settings.gemini_model,
            max_output_tokens=settings.gemini_max_output_tokens,
            timeout_seconds=settings.gemini_timeout_seconds,
        )) as generator:
            path = run_evaluation(
                generator, dataset_path=args.dataset, settings=settings,
                repo=Path.cwd(), output_dir=args.output_dir,
            )
            print(path)
            run = Run.model_validate_json(path.read_bytes())
            return 1 if any(case.status == "error" for case in run.cases) else 0
    except Exception:
        # Configuration/provider/IO errors may contain credentials or response bodies.
        parser.exit(1, "Evaluation failed; check configuration, dataset and file access.\n")


if __name__ == "__main__":
    raise SystemExit(main())
