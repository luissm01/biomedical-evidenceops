from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from evidenceops.config import Settings
from evidenceops.database import create_database
from evidenceops.generation import GeneratedContent
from evidenceops.main import create_app
from evidenceops.models import Question


class _TestDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVIDENCEOPS_",
        extra="ignore",
        frozen=True,
    )

    test_database_url: PostgresDsn


TEST_API_KEY = "test-api-key-0123456789"
AUTH_HEADERS = {"X-API-Key": TEST_API_KEY}


def allow_protected_endpoints(app) -> None:
    """For apps used without lifespan: bypass API key and rate limit checks."""
    from evidenceops.security import enforce_llm_rate_limit, require_api_key

    app.dependency_overrides[require_api_key] = lambda: "test"
    app.dependency_overrides[enforce_llm_rate_limit] = lambda: None


class FakeGenerator:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(
        self, question_text: str, *, system_instruction: str | None = None,
    ) -> GeneratedContent:
        self.calls.append(question_text)

        return GeneratedContent(
            answer="Respuesta generada para el test",
            limitations=["Limitación de prueba"],
        )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    test_database_url = _TestDatabaseSettings().test_database_url
    if make_url(str(test_database_url)).database != "evidenceops_test":
        pytest.fail(
            "EVIDENCEOPS_TEST_DATABASE_URL must point to the evidenceops_test database"
        )
    return Settings(database_url=str(test_database_url), gemini_api_key=None, api_keys=(TEST_API_KEY,))


@pytest.fixture(scope="session")
def migrated_database(test_settings: Settings) -> None:
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", test_settings.database_dsn)
    command.upgrade(alembic_config, "head")


@pytest.fixture
def clean_questions(
    test_settings: Settings, migrated_database: None
) -> Iterator[None]:
    engine, session_factory = create_database(test_settings)

    def delete_all_questions() -> None:
        with session_factory.begin() as session:
            session.execute(delete(Question))

    delete_all_questions()
    try:
        yield
    finally:
        delete_all_questions()
        engine.dispose()


@pytest.fixture
def client(
    test_settings: Settings,
    clean_questions: None,
    fake_generator: FakeGenerator,
) -> Iterator[TestClient]:
    with TestClient(
        create_app(
            test_settings,
            generator=fake_generator,
        ),
        headers=AUTH_HEADERS,
    ) as test_client:
        yield test_client


@pytest.fixture
def fake_generator() -> FakeGenerator:
    return FakeGenerator()
