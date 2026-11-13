"""Liveness and readiness semantics (D037).

Liveness answers "is this process able to serve at all?" and checks nothing
external: if it failed when PostgreSQL is down, an orchestrator would restart
every healthy API instance, turning a database outage into an API outage and a
restart storm, without fixing anything. Readiness answers "should traffic be
sent here now?": it checks the dependencies the endpoints need, and a 503
only takes the instance out of rotation until they recover.
"""

from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"


def expected_migration_heads() -> frozenset[str]:
    """Head revision(s) shipped with this code, read from the migration scripts."""
    return frozenset(ScriptDirectory(str(_MIGRATIONS)).get_heads())


def check_readiness(engine: Engine, expected_heads: frozenset[str]) -> dict[str, str]:
    """Return content-free check states; never exception text or URLs."""
    try:
        with engine.connect() as connection:
            current = frozenset(connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars())
    except ProgrammingError:  # connected, but alembic_version does not exist
        return {"database": "ok", "migrations": "missing"}
    except SQLAlchemyError:
        return {"database": "unavailable", "migrations": "unknown"}
    return {"database": "ok", "migrations": "ok" if current == expected_heads else "outdated"}
