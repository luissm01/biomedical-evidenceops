"""Thin local CLI: parse input, compose resources, print a safe JSON summary."""

import argparse
import json
import signal
import sys
import threading
from functools import partial

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from evidenceops import jobs
from evidenceops.config import JobSettings, PubMedSettings, Settings
from evidenceops.database import create_database
from evidenceops.ingestion import ingest_pubmed
from evidenceops.metrics import JobMetrics
from evidenceops.observability import configure_logging
from evidenceops.pubmed import PubMedClient
from evidenceops.worker import IngestionWorker


def _pmid(value: str) -> str:
    if not value.isdecimal():
        raise argparse.ArgumentTypeError("PMIDs must be nonempty decimal strings")
    return value


def _query(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("query must not be empty")
    return value.strip()


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidenceops")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Ingest PubMed metadata and abstracts")
    modes = ingest.add_mutually_exclusive_group(required=True)
    modes.add_argument("--pmid", type=_pmid, nargs="+", action="extend", dest="pmids")
    modes.add_argument("--query", type=_query)
    ingest.add_argument("--limit", type=int)
    worker = commands.add_parser("worker", help="Process queued ingestion jobs until stopped")
    worker.add_argument("--metrics-port", type=_port,
                        help="Expose worker Prometheus metrics on this local port")
    args = parser.parse_args(argv)
    if args.command == "worker":
        return _run_worker(args.metrics_port)
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


def _install_stop_handlers(stop: threading.Event) -> None:
    """First SIGINT/SIGTERM: finish the current job, then exit.

    A second signal raises KeyboardInterrupt inside the job; the worker
    releases it back to the queue before exiting.
    """
    def handle(_signum: int, _frame: object) -> None:
        if stop.is_set():
            raise KeyboardInterrupt
        stop.set()

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)


def _run_worker(metrics_port: int | None) -> int:
    configure_logging()
    engine = None
    metrics_server = None
    try:
        settings = Settings()
        pubmed_settings = PubMedSettings()
        job_settings = JobSettings()
        engine, session_factory = create_database(settings)
        metrics = JobMetrics(partial(jobs.count_by_status, session_factory))
        if metrics_port is not None:
            from prometheus_client import start_http_server

            metrics_server, _thread = start_http_server(
                metrics_port, addr="127.0.0.1", registry=metrics.registry,
            )
        stop = threading.Event()
        _install_stop_handlers(stop)
        with PubMedClient(pubmed_settings) as client:
            IngestionWorker(session_factory, client, job_settings, metrics=metrics, stop=stop).run()
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValidationError, SQLAlchemyError):
        print(json.dumps({"event": "worker.setup_failed", "cause": "configuration_or_database_error"}), file=sys.stderr)
        return 1
    finally:
        if metrics_server is not None:
            metrics_server.shutdown()
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
