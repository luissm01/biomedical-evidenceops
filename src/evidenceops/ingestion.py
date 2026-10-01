"""Reusable synchronous ingestion with batch and document failure isolation."""

import logging
from dataclasses import asdict, dataclass, field
from time import perf_counter
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.publications import upsert_publication
from evidenceops.pubmed import PUBMED_BATCH_SIZE, PubMedClient, PubMedError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IngestionFailure:
    source_id: str | None
    cause: str


@dataclass(slots=True)
class IngestionSummary:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = "pubmed"
    requested: int = 0
    unique: int = 0
    batches: int = 0
    created: int = 0
    updated: int = 0
    omitted: int = 0
    failed: int = 0
    unidentified_invalid: int = 0
    duration_ms: float = 0
    failures: list[IngestionFailure] = field(default_factory=list)

    def fail(self, source_id: str | None, cause: str) -> None:
        self.failed += 1
        self.failures.append(IngestionFailure(source_id, cause))

    def as_dict(self) -> dict:
        return asdict(self)


def ingest_pubmed(
    client: PubMedClient,
    session_factory: sessionmaker[Session],
    *,
    pmids: list[str] | None = None,
    query: str | None = None,
    limit: int | None = None,
) -> IngestionSummary:
    """Persist each valid document independently; count only committed writes.

    Search failure is one failed discovery operation, with no known PMIDs.
    Unidentifiable invalid records are additional failures, separate from
    requested PMIDs absent from the response; they cannot safely be matched.
    """
    if (pmids is None) == (query is None):
        raise ValueError("Provide either pmids or query")
    if pmids is not None:
        if limit is not None or not pmids or any(
            not isinstance(pmid, str) or not pmid.isdecimal() for pmid in pmids
        ):
            raise ValueError("Provide nonempty decimal PMIDs without limit")
    elif not query.strip() or limit is None or not 1 <= limit <= 100:
        raise ValueError("Provide a nonempty query and limit between 1 and 100")

    summary = IngestionSummary()
    started = perf_counter()
    unexpected_error = False
    logger.info("ingestion.started", extra={"source": summary.source, "run_id": summary.run_id})
    try:
        if query is not None:
            try:
                pmids = client.search(query, limit=limit)
            except PubMedError as exc:
                summary.fail(None, f"search_{exc.cause}")
                return summary
        summary.requested = len(pmids)
        ids = list(dict.fromkeys(pmids))
        summary.unique = len(ids)
        summary.omitted = summary.requested - summary.unique
        for offset in range(0, len(ids), PUBMED_BATCH_SIZE):
            batch = ids[offset:offset + PUBMED_BATCH_SIZE]
            summary.batches += 1
            try:
                fetched = client.fetch(batch)
            except PubMedError as exc:
                for pmid in batch:
                    summary.fail(pmid, f"fetch_{exc.cause}")
                continue
            for invalid in fetched.invalid_records:
                identified = bool(invalid.source_id and invalid.source_id.isdecimal())
                if not identified:
                    summary.unidentified_invalid += 1
                summary.fail(invalid.source_id if identified else None, "invalid_record")
            for document in fetched.documents:
                candidate_id = uuid4()
                try:
                    with session_factory.begin() as session:
                        publication = upsert_publication(session, document, candidate_id=candidate_id)
                        created = publication.id == candidate_id
                except SQLAlchemyError:
                    summary.fail(document.source_id, "persistence_error")
                    continue
                if created:
                    summary.created += 1
                else:
                    summary.updated += 1
        return summary
    except Exception:
        unexpected_error = True
        raise
    finally:
        summary.duration_ms = round((perf_counter() - started) * 1000, 3)
        fields = summary.as_dict()
        fields.pop("failures")
        # LogRecord.created is the timestamp; keep our count under another key.
        fields["created_count"] = fields.pop("created")
        fields["outcome"] = "error" if summary.failed or unexpected_error else "success"
        if unexpected_error:
            fields["cause"] = "unexpected_application_error"
        logger.info("ingestion.finished", extra=fields)
