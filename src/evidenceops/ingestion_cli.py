"""Thin local CLI: parse input, compose resources, print a safe JSON summary."""

import argparse
import json
import sys

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from evidenceops.config import PubMedSettings, Settings
from evidenceops.database import create_database
from evidenceops.ingestion import ingest_pubmed
from evidenceops.observability import configure_logging
from evidenceops.pubmed import PubMedClient


def _pmid(value: str) -> str:
    if not value.isdecimal():
        raise argparse.ArgumentTypeError("PMIDs must be nonempty decimal strings")
    return value


def _query(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("query must not be empty")
    return value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidenceops")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Ingest PubMed metadata and abstracts")
    modes = ingest.add_mutually_exclusive_group(required=True)
    modes.add_argument("--pmid", type=_pmid, nargs="+", action="extend", dest="pmids")
    modes.add_argument("--query", type=_query)
    ingest.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    if args.query is not None:
        if args.limit is None or not 1 <= args.limit <= 100:
            parser.error("--query requires --limit between 1 and 100")
    elif args.limit is not None:
        parser.error("--limit is only valid with --query")

    configure_logging()
    engine = None
    try:
        settings = Settings()
        pubmed_settings = PubMedSettings()
        engine, session_factory = create_database(settings)
        with PubMedClient(pubmed_settings) as client:
            summary = ingest_pubmed(
                client, session_factory, pmids=args.pmids, query=args.query, limit=args.limit,
            )
        print(json.dumps(summary.as_dict(), ensure_ascii=False, allow_nan=False))
        return 1 if summary.failed else 0
    except (ValidationError, SQLAlchemyError):
        print(json.dumps({"event": "ingestion.setup_failed", "cause": "configuration_or_database_error"}), file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
