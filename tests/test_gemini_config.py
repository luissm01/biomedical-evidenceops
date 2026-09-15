import pytest
from pydantic import ValidationError

from evidenceops.config import Settings


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ["API_KEY", "MODEL", "MAX_OUTPUT_TOKENS", "TIMEOUT_SECONDS"]:
        monkeypatch.delenv(f"EVIDENCEOPS_GEMINI_{name}", raising=False)
    monkeypatch.setenv("EVIDENCEOPS_DATABASE_URL", "postgresql+psycopg://localhost/test")


def test_gemini_defaults_and_optional_key():
    settings = Settings()
    assert settings.gemini_api_key is None
    assert settings.gemini_model == "gemini-3.6-flash"
    assert settings.gemini_max_output_tokens == 2048
    assert settings.gemini_timeout_seconds == 60


def test_prefixed_environment_overrides_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("EVIDENCEOPS_GEMINI_MODEL=from-dotenv\n")
    assert Settings().gemini_model == "from-dotenv"
    monkeypatch.setenv("EVIDENCEOPS_GEMINI_API_KEY", "test-only-key")
    monkeypatch.setenv("EVIDENCEOPS_GEMINI_MODEL", " other-model ")
    monkeypatch.setenv("EVIDENCEOPS_GEMINI_MAX_OUTPUT_TOKENS", "256")
    monkeypatch.setenv("EVIDENCEOPS_GEMINI_TIMEOUT_SECONDS", "12.5")
    settings = Settings()
    assert settings.gemini_model == "other-model"
    assert settings.gemini_max_output_tokens == 256
    assert settings.gemini_timeout_seconds == 12.5
    assert settings.gemini_api_key.get_secret_value() == "test-only-key"
    assert "test-only-key" not in repr(settings)
    assert "test-only-key" not in settings.model_dump_json()


@pytest.mark.parametrize("name,value", [
    ("MODEL", "  "), ("MAX_OUTPUT_TOKENS", "0"),
    ("MAX_OUTPUT_TOKENS", "-1"), ("MAX_OUTPUT_TOKENS", "1.5"),
    ("TIMEOUT_SECONDS", "0"), ("TIMEOUT_SECONDS", "-1"),
    ("TIMEOUT_SECONDS", "nan"), ("TIMEOUT_SECONDS", "inf"),
])
def test_rejects_invalid_gemini_configuration(monkeypatch, name, value):
    monkeypatch.setenv(f"EVIDENCEOPS_GEMINI_{name}", value)
    with pytest.raises(ValidationError):
        Settings()


def test_validation_message_hides_invalid_input(monkeypatch):
    monkeypatch.setenv("EVIDENCEOPS_GEMINI_TIMEOUT_SECONDS", "test-only-secret")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert "test-only-secret" not in str(caught.value)


@pytest.mark.parametrize("key", ["", "  "])
def test_blank_key_is_unconfigured(monkeypatch, key):
    monkeypatch.setenv("EVIDENCEOPS_GEMINI_API_KEY", key)
    assert Settings().gemini_api_key is None
