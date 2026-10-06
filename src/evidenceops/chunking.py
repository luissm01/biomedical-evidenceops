"""Pure, reproducible whole-publication representation; no model or storage I/O."""

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from evidenceops.biomedical import BiomedicalDocument


CHUNKING_STRATEGY = "whole-publication-v1"


@dataclass(frozen=True, slots=True)
class RetrievableUnit:
    unit_id: str
    publication_id: UUID
    source: str
    source_id: str
    strategy: str
    chunk_index: int
    title: str
    abstract: str | None
    text: str
    content_fingerprint: str
    authors: tuple[str, ...]
    journal: str | None
    doi: str | None
    publication_year: int | None
    source_url: str | None


def build_retrievable_unit(
    document: BiomedicalDocument, *, publication_id: UUID,
) -> RetrievableUnit | None:
    """Return one unit, or None when title and abstract contain only whitespace.

    Join only fields containing content, preserving their input text exactly.
    A blank title is omitted from text; a blank abstract counts as absent.
    Identity is SHA-256 of compact UTF-8 JSON [source, source_id, strategy, 0],
    independent of content and of the database's publication UUID. The content
    fingerprint is SHA-256 of the exact represented text in UTF-8. Bump the
    strategy constant whenever representation rules change.
    """
    if not document.source.strip() or not document.source_id.strip():
        raise ValueError("Publication source and source_id must contain content")

    abstract = document.abstract
    if abstract is not None and not abstract.strip():
        abstract = None
    if not document.title.strip() and abstract is None:
        return None

    text = "\n\n".join(
        field for field in (document.title, abstract)
        if field is not None and field.strip()
    )
    identity = json.dumps(
        [document.source, document.source_id, CHUNKING_STRATEGY, 0],
        ensure_ascii=False, separators=(",", ":"),
    )
    return RetrievableUnit(
        unit_id=sha256(identity.encode("utf-8")).hexdigest(),
        publication_id=publication_id,
        source=document.source,
        source_id=document.source_id,
        strategy=CHUNKING_STRATEGY,
        chunk_index=0,
        title=document.title,
        abstract=abstract,
        text=text,
        content_fingerprint=sha256(text.encode("utf-8")).hexdigest(),
        authors=tuple(document.authors),
        journal=document.journal,
        doi=document.doi,
        publication_year=document.publication_year,
        source_url=document.source_url,
    )
