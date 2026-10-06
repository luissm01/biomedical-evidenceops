"""Explicit manual MedCPT smoke test over already ingested public publications."""

import argparse
from dataclasses import asdict
import json

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select

from evidenceops.config import Settings
from evidenceops.database import create_database
from evidenceops.embeddings import LocalMedCPT
from evidenceops.models import Publication
from evidenceops.retrieval import index_publication, search


class _DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EVIDENCEOPS_", extra="ignore")
    database_url: PostgresDsn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--published-from", type=int)
    parser.add_argument("--index-limit", type=int, default=5)
    args = parser.parse_args()
    if args.index_limit <= 0 or args.top_k <= 0 or not args.query.strip():
        parser.error("index-limit/top-k must be positive and query must contain text")
    settings = Settings(database_url=_DatabaseSettings().database_url)
    engine, sessions = create_database(settings)
    encoder = LocalMedCPT()
    try:
        with sessions() as session:
            ids = list(session.scalars(select(Publication.id).order_by(Publication.source, Publication.source_id).limit(args.index_limit)))
        for publication_id in ids:
            print(json.dumps({"publication_id": str(publication_id), "status": index_publication(sessions, publication_id, encoder)}))
        results = search(sessions, encoder, query=args.query, top_k=args.top_k, published_from=args.published_from)
        print(json.dumps([asdict(result) for result in results], default=str, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
