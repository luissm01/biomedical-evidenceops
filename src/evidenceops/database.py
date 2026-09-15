from collections.abc import Iterator
from typing import cast

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.config import Settings


def create_database(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(str(settings.database_url), pool_pre_ping=True)
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
