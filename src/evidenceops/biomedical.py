"""Source-independent bibliographic document contract."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BiomedicalDocument:
    source: str
    source_id: str
    title: str
    abstract: str | None
    authors: list[str]
    journal: str | None
    doi: str | None
    publication_year: int | None
    source_url: str | None
