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


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    test_database_url = _TestDatabaseSettings().test_database_url
    if make_url(str(test_database_url)).database != "evidenceops_test":
        pytest.fail(
            "EVIDENCEOPS_TEST_DATABASE_URL must point to the evidenceops_test database"
        )
    return Settings(database_url=test_database_url)


@pytest.fixture(scope="session")
def migrated_database(test_settings: Settings) -> None:
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", str(test_settings.database_url))
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
def client(test_settings: Settings, clean_questions: None) -> Iterator[TestClient]:
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
