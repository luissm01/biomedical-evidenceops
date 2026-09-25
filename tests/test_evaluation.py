import hashlib
import json
import subprocess
import sys

import pytest

from evidenceops import evaluation
from evidenceops.config import GenerationSettings
from evidenceops.generation import GeneratedContent, GenerationError, GenerationErrorCause


@pytest.fixture
def dataset(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "dataset_version": "test", "cases": [
            {"id": str(i), "question": f"Question {i}",
             "reference_facts": ["SECRET RUBRIC"],
             "expected_behavior": ["SECRET RUBRIC"],
             "forbidden_claims": ["SECRET RUBRIC"]} for i in range(3)
        ],
    }))
    return path


@pytest.fixture
def settings():
    return GenerationSettings(_env_file=None, gemini_api_key=None,
                              gemini_model="fake", gemini_max_output_tokens=123,
                              gemini_timeout_seconds=7)


class FakeGenerator:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def generate(self, question):
        self.calls.append(question)
        if len(self.calls) == 2 and self.error is not None:
            raise self.error
        return GeneratedContent(answer=question, limitations=[])


def execute(tmp_path, dataset, settings, monkeypatch, generator):
    monkeypatch.setattr(evaluation, "git_state", lambda _: ("a" * 40, True))
    return evaluation.run_evaluation(generator, dataset_path=dataset,
                                     settings=settings, repo=tmp_path,
                                     output_dir=tmp_path / "runs")


def test_run_metadata_inputs_and_promotion(tmp_path, dataset, settings, monkeypatch):
    fake = FakeGenerator()
    path = execute(tmp_path, dataset, settings, monkeypatch, fake)
    run = evaluation.Run.model_validate_json(path.read_bytes())
    assert fake.calls == [f"Question {i}" for i in range(3)]
    assert [case.output.answer for case in run.cases] == fake.calls
    assert run.model == "fake" and run.max_output_tokens == 123
    assert run.timeout_seconds == 7 and run.working_tree_dirty
    assert run.git_commit == "a" * 40
    assert run.timestamp_utc.utcoffset().total_seconds() == 0
    assert run.dataset_sha256 == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert run.dataset_version == "test"
    assert path.stem == str(run.run_id)
    assert "SECRET RUBRIC" not in path.read_text()
    baseline = tmp_path / "baselines" / "initial.json"
    evaluation.promote_baseline(path, baseline, dataset)
    assert baseline.read_bytes() == path.read_bytes()
    with pytest.raises(FileExistsError):
        evaluation.promote_baseline(path, baseline, dataset)


@pytest.mark.parametrize("error,cause", [
    (GenerationError(cause, "SECRET KEY/BODY") , cause)
    for cause in GenerationErrorCause
] + [(RuntimeError("SECRET KEY/BODY"), GenerationErrorCause.UNKNOWN)])
def test_errors_are_safe_and_continue(tmp_path, dataset, settings, monkeypatch, error, cause):
    fake = FakeGenerator(error)
    path = execute(tmp_path, dataset, settings, monkeypatch, fake)
    run = evaluation.Run.model_validate_json(path.read_bytes())
    assert len(fake.calls) == 3
    assert [case.status for case in run.cases] == ["success", "error", "success"]
    assert run.cases[1].error == cause
    assert "SECRET" not in path.read_text()
    with pytest.raises(ValueError):
        evaluation.promote_baseline(path, tmp_path / "baseline.json", dataset)


@pytest.mark.parametrize("change", ["missing", "duplicate", "question", "hash", "version", "output"])
def test_rejects_invalid_baseline(tmp_path, dataset, settings, monkeypatch, change):
    path = execute(tmp_path, dataset, settings, monkeypatch, FakeGenerator())
    raw = json.loads(path.read_text())
    if change == "missing":
        raw["cases"].pop()
    elif change == "duplicate":
        raw["cases"][1] = raw["cases"][0]
    elif change == "question":
        raw["cases"][0]["question"] = "Changed"
    elif change == "hash":
        raw["dataset_sha256"] = "b" * 64
    elif change == "version":
        raw["dataset_version"] = "other"
    else:
        raw["cases"][0]["output"] = None
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        evaluation.promote_baseline(path, tmp_path / "baseline.json", dataset)
    assert not (tmp_path / "baseline.json").exists()


def test_interruption_preserves_partial_run(tmp_path, dataset, settings, monkeypatch):
    with pytest.raises(KeyboardInterrupt):
        execute(tmp_path, dataset, settings, monkeypatch, FakeGenerator(KeyboardInterrupt()))
    path, = (tmp_path / "runs").glob("*.json")
    assert len(json.loads(path.read_text())["cases"]) == 1
    with pytest.raises(ValueError):
        evaluation.promote_baseline(path, tmp_path / "baseline.json", dataset)


def test_cli_requires_live_before_loading_settings(monkeypatch):
    def unexpected():
        pytest.fail("Settings should not be read without --live")
    monkeypatch.setattr(evaluation, "GenerationSettings", unexpected)
    with pytest.raises(SystemExit) as exc:
        evaluation.main(["run"])
    assert exc.value.code == 2


def test_cli_live_uses_effective_settings_and_closes(tmp_path, dataset, settings, monkeypatch):
    from evidenceops import gemini
    fake = FakeGenerator()
    closed = []
    fake.close = lambda: closed.append(True)
    from pydantic import SecretStr
    settings = settings.model_copy(update={"gemini_api_key": SecretStr("test-key")})
    monkeypatch.setattr(evaluation, "GenerationSettings", lambda: settings)
    monkeypatch.setattr(evaluation, "git_state", lambda _: ("a" * 40, False))
    def create(**kwargs):
        assert kwargs == dict(api_key="test-key", model="fake", max_output_tokens=123, timeout_seconds=7)
        return fake
    monkeypatch.setattr(gemini, "GeminiGenerator", create)
    assert evaluation.main(["run", "--live", "--dataset", str(dataset),
                            "--output-dir", str(tmp_path / "runs")]) == 0
    assert closed == [True] and len(fake.calls) == 3


def test_generation_settings_need_no_database_or_key(monkeypatch):
    monkeypatch.delenv("EVIDENCEOPS_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("EVIDENCEOPS_DATABASE_URL", "invalid")
    assert GenerationSettings(_env_file=None).gemini_api_key is None


def test_cli_missing_key_is_safe(dataset, settings, monkeypatch, capsys):
    monkeypatch.setattr(evaluation, "GenerationSettings", lambda: settings)
    monkeypatch.setattr(evaluation, "git_state", lambda _: ("a" * 40, False))
    with pytest.raises(SystemExit) as exc:
        evaluation.main(["run", "--live", "--dataset", str(dataset)])
    assert exc.value.code == 2
    assert "EVIDENCEOPS_GEMINI_API_KEY is required" in capsys.readouterr().err


@pytest.mark.parametrize("invalid", ["empty", "duplicate"])
def test_invalid_dataset_prevents_inference(tmp_path, dataset, settings, monkeypatch, invalid):
    raw = json.loads(dataset.read_text())
    raw["cases"] = [] if invalid == "empty" else [raw["cases"][0]] * 2
    dataset.write_text(json.dumps(raw))
    fake = FakeGenerator()
    with pytest.raises(ValueError):
        execute(tmp_path, dataset, settings, monkeypatch, fake)
    assert fake.calls == []


def test_cli_failure_exit_and_close(tmp_path, dataset, settings, monkeypatch):
    from evidenceops import gemini
    from pydantic import SecretStr
    fake = FakeGenerator(RuntimeError("secret"))
    closed = []
    fake.close = lambda: closed.append(True)
    settings = settings.model_copy(update={"gemini_api_key": SecretStr("test-key")})
    monkeypatch.setattr(evaluation, "GenerationSettings", lambda: settings)
    monkeypatch.setattr(evaluation, "git_state", lambda _: ("a" * 40, False))
    monkeypatch.setattr(gemini, "GeminiGenerator", lambda **_: fake)
    assert evaluation.main(["run", "--live", "--dataset", str(dataset),
                            "--output-dir", str(tmp_path / "runs")]) == 1
    assert closed == [True]


def test_git_state_clean_and_untracked(tmp_path):
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)
    git("init")
    git("-c", "user.name=Test", "-c", "user.email=test@example.com",
        "commit", "--allow-empty", "-m", "test")
    commit, dirty = evaluation.git_state(tmp_path)
    assert len(commit) == 40 and dirty is False
    (tmp_path / "untracked").write_text("change")
    assert evaluation.git_state(tmp_path) == (commit, True)


def test_runner_import_does_not_load_api_database_or_sdk():
    subprocess.run([
        sys.executable, "-c",
        "import sys; import evidenceops.evaluation; "
        "assert not any(name in sys.modules for name in "
        "('fastapi', 'sqlalchemy', 'evidenceops.main', 'evidenceops.gemini'))",
    ], check=True, capture_output=True)
