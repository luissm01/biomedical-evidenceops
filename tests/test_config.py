import asyncio

import pytest
from pydantic import ValidationError

from evidenceops.config import Settings
from evidenceops.main import create_app


def test_accepts_psycopg_database_url() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://user:password@localhost/evidenceops"
    )

    assert settings.database_url.scheme == "postgresql+psycopg"


@pytest.mark.parametrize(
    "database_url",
    [
        "not-a-url",
        "sqlite:///evidenceops.db",
        "postgresql://user:password@localhost/evidenceops",
    ],
)
def test_rejects_invalid_database_url(database_url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=database_url)


def test_requires_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EVIDENCEOPS_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_invalid_database_url_prevents_application_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVIDENCEOPS_DATABASE_URL", "not-a-database-url")
    application = create_app()

    async def run_lifespan() -> None:
        async with application.router.lifespan_context(application):
            pass

    with pytest.raises(ValidationError):
        asyncio.run(run_lifespan())
