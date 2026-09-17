from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from evidenceops.config import Settings
from evidenceops.main import create_app


@pytest.fixture
def resources(monkeypatch):
    engine = Mock()
    engine.connect.return_value.__enter__ = Mock()
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(
        "evidenceops.main.create_database", Mock(return_value=(engine, Mock()))
    )
    constructor = Mock()
    monkeypatch.setattr("evidenceops.main.GeminiGenerator", constructor)
    return engine, constructor


def settings(key=None):
    return Settings(
        _env_file=None,
        database_url="postgresql+psycopg://localhost/evidenceops_test",
        gemini_api_key=key,
    )


def test_injected_generator_is_not_closed(resources, fake_generator):
    engine, constructor = resources
    fake_generator.close = Mock()
    with TestClient(create_app(settings(), generator=fake_generator)) as client:
        assert client.app.state.generator is fake_generator
    fake_generator.close.assert_not_called()
    constructor.assert_not_called()
    engine.dispose.assert_called_once()


@pytest.mark.parametrize("close_fails", [False, True])
def test_owned_generator_is_closed_and_engine_disposed(resources, close_fails):
    engine, constructor = resources
    if close_fails:
        constructor.return_value.close.side_effect = RuntimeError("close failed")

    def run_app():
        with TestClient(create_app(settings("test-key"))) as client:
            assert client.app.state.generator is constructor.return_value
            constructor.return_value.close.assert_not_called()

    if close_fails:
        with pytest.raises(RuntimeError, match="close failed"):
            run_app()
    else:
        run_app()
    constructor.return_value.close.assert_called_once()
    constructor.return_value.generate.assert_not_called()
    engine.dispose.assert_called_once()


def test_missing_key_prevents_startup(resources):
    engine, constructor = resources
    with pytest.raises(RuntimeError, match="EVIDENCEOPS_GEMINI_API_KEY is required"):
        with TestClient(create_app(settings())):
            pass
    constructor.assert_not_called()
    engine.dispose.assert_called_once()
