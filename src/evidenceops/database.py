from collections.abc import Iterator
from typing import cast

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.config import Settings


def create_database(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    # pre_ping replaces connections broken by a database restart on checkout,
    # so the API recovers without restarting. Both timeouts bound how long a
    # request can wait on an unavailable or stuck database (D037).
    engine = create_engine(
        settings.database_dsn,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "options": f"-c statement_timeout={settings.database_statement_timeout_ms}",
        },
    )
    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    return engine, session_factory


def get_session(request: Request) -> Iterator[Session]:
    session_factory = cast(
        sessionmaker[Session], request.app.state.session_factory
    )
    with session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
