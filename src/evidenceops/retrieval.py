"""Index and search a small exact pgvector corpus; no HTTP or generation."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from evidenceops.chunking import RetrievableUnit, build_retrievable_unit
from evidenceops.embeddings import (
    EmbeddingCompatibilityError, MedCPTConfig, MedCPTEncoder, article_inputs,
    validate_config, validate_vector,
)
from evidenceops.models import Publication, UnitEmbedding
from evidenceops.publications import as_biomedical_document


def _unit(publication: Publication) -> RetrievableUnit | None:
    return build_retrievable_unit(as_biomedical_document(publication), publication_id=publication.id)


def _compatible(row: UnitEmbedding, config: MedCPTConfig) -> None:
    if row.configuration != config.metadata() or row.strategy != config.strategy:
        raise EmbeddingCompatibilityError("Corpus configuration differs; explicitly rebuild incompatible rows")


def index_publication(
    sessions: sessionmaker[Session], publication_id: UUID, encoder: MedCPTEncoder,
    *, replace_incompatible: bool = False,
) -> str:
    """Return indexed/unchanged/omitted. Own commits, no DB connection during encoding.

    Serialize the final write on the publication. If the source changes during
    encoding, abort rather than persist a vector for a superseded snapshot.
    Explicit replacement is per publication; search rejects a mixed corpus
    until all incompatible rows have been rebuilt.
    """
    validate_config(encoder.config)
    with sessions.begin() as session:
        publication = session.get(Publication, publication_id)
        if publication is None:
            raise ValueError("Publication does not exist")
        unit = _unit(publication)
        existing = session.scalar(select(UnitEmbedding).where(UnitEmbedding.publication_id == publication_id))
        if existing is not None and not replace_incompatible:
            _compatible(existing, encoder.config)
        if unit is not None and existing is not None:
            if (existing.unit_id == unit.unit_id
                    and existing.content_fingerprint == unit.content_fingerprint
                    and existing.configuration == encoder.config.metadata()
                    and existing.strategy == unit.strategy
                    and article_inputs(existing.source_title, existing.source_abstract)
                    == article_inputs(unit.title, unit.abstract)):
                # Exact source fields can change without changing represented text.
                existing.source_title = publication.title
                existing.source_abstract = publication.abstract
                return "unchanged"

    vector = validate_vector(encoder.encode_article(unit)) if unit is not None else None
    with sessions.begin() as session:
        publication = session.scalar(select(Publication).where(Publication.id == publication_id).with_for_update())
        if publication is None or _unit(publication) != unit:
            raise RuntimeError("Publication changed during indexing; retry explicitly")
        existing = session.scalar(select(UnitEmbedding).where(UnitEmbedding.publication_id == publication_id))
        if existing is not None and not replace_incompatible:
            _compatible(existing, encoder.config)
        if unit is None:
            session.execute(delete(UnitEmbedding).where(UnitEmbedding.publication_id == publication_id))
            return "omitted"
        if existing is not None:
            session.delete(existing)
            session.flush()
        session.add(UnitEmbedding(
            unit_id=unit.unit_id, publication_id=publication_id, strategy=unit.strategy,
            content_fingerprint=unit.content_fingerprint, text=unit.text,
            source_title=publication.title, source_abstract=publication.abstract,
            configuration=encoder.config.metadata(), vector=vector,
        ))
    return "indexed"


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    unit: RetrievableUnit
    score: float


def search(
    sessions: sessionmaker[Session], encoder: MedCPTEncoder, *, query: str,
    top_k: int, published_from: int | None = None,
) -> list[RetrievalResult]:
    """Exact dot-product ranking, descending; stable unit_id tie break.

    Empty/filtered corpus returns []. Unknown year fails a temporal filter.
    Fewer candidates returns fewer results, without padding or score threshold.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must contain text")
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if published_from is not None and (type(published_from) is not int or published_from <= 0):
        raise ValueError("published_from must be a positive year")
    validate_config(encoder.config)
    # Encode outside DB transaction. Empty corpus still validates the encoder output.
    vector = validate_vector(encoder.encode_query(query.strip()))
    with sessions() as session:
        incompatible = session.scalar(select(UnitEmbedding.unit_id).where(
            (UnitEmbedding.configuration != encoder.config.metadata())
            | (UnitEmbedding.strategy != encoder.config.strategy)
        ).limit(1))
        if incompatible is not None:
            raise EmbeddingCompatibilityError("Corpus configuration differs; rebuild before search")
        distance = UnitEmbedding.vector.max_inner_product(vector)
        statement = select(Publication, UnitEmbedding, (-distance).label("score")).join(
            UnitEmbedding, UnitEmbedding.publication_id == Publication.id,
        ).where(
            UnitEmbedding.configuration == encoder.config.metadata(),
            UnitEmbedding.strategy == encoder.config.strategy,
            UnitEmbedding.source_title == Publication.title,
            UnitEmbedding.source_abstract.is_not_distinct_from(Publication.abstract),
        )
        if published_from is not None:
            statement = statement.where(Publication.publication_year >= published_from)
        rows = session.execute(statement.order_by(distance, UnitEmbedding.unit_id).limit(top_k)).all()
        results = []
        for publication, embedding, score in rows:
            unit = _unit(publication)
            # Also guard stored identity/fingerprint/text against inconsistent rows.
            if (unit is None or unit.unit_id != embedding.unit_id
                    or unit.content_fingerprint != embedding.content_fingerprint
                    or unit.text != embedding.text):
                raise EmbeddingCompatibilityError("Stored unit differs from source; reindex")
            results.append(RetrievalResult(unit=unit, score=float(score)))
        return results
