"""Translate PubMed E-utilities XML into source-independent documents."""

import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from evidenceops.biomedical import BiomedicalDocument


class PubMedParseError(Exception):
    """An E-utilities response is not usable PubMed XML."""


@dataclass(frozen=True, slots=True)
class InvalidPubMedRecord:
    source_id: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ParsedPubMedBatch:
    documents: list[BiomedicalDocument]
    invalid_records: list[InvalidPubMedRecord]


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None


def _year(article: ET.Element) -> int | None:
    pub_date = article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate")
    candidates = (
        _text(pub_date.find("Year")) if pub_date is not None else None,
        _text(pub_date.find("MedlineDate")) if pub_date is not None else None,
        _text(article.find("./MedlineCitation/Article/ArticleDate/Year")),
    )
    for candidate in candidates:
        if candidate and (match := re.search(r"\b(?:18|19|20|21)\d{2}\b", candidate)):
            return int(match.group())
    return None


def _authors(article: ET.Element) -> list[str]:
    result: list[str] = []
    for author in article.findall("./MedlineCitation/Article/AuthorList/Author"):
        collective = _text(author.find("CollectiveName"))
        if collective:
            result.append(collective)
            continue
        last = _text(author.find("LastName"))
        given = _text(author.find("ForeName")) or _text(author.find("Initials"))
        suffix = _text(author.find("Suffix"))
        if last:
            result.append(" ".join(part for part in (given, last, suffix) if part))
    return result


def _abstract(article: ET.Element) -> str | None:
    sections: list[str] = []
    for section in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
        value = _text(section)
        if value:
            label = (section.get("Label") or "").strip()
            sections.append(f"{label}: {value}" if label else value)
    return "\n".join(sections) or None


def _doi(article: ET.Element) -> str | None:
    for path in (
        "./PubmedData/ArticleIdList/ArticleId",
        "./MedlineCitation/Article/ELocationID",
    ):
        for item in article.findall(path):
            if item.get("IdType") == "doi" or item.get("EIdType") == "doi":
                value = _text(item)
                if value:
                    return value
    return None


def parse_pubmed_xml(xml: bytes) -> ParsedPubMedBatch:
    """Reject broken envelopes; keep valid articles beside invalid records."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise PubMedParseError("Malformed PubMed XML") from exc
    if root.tag != "PubmedArticleSet":
        raise PubMedParseError("Unexpected PubMed XML root")
    if root.find("ERROR") is not None:
        raise PubMedParseError("PubMed returned an error")

    documents: list[BiomedicalDocument] = []
    invalid: list[InvalidPubMedRecord] = []
    for article in root.findall("PubmedArticle"):
        pmid = _text(article.find("./MedlineCitation/PMID"))
        title = _text(article.find("./MedlineCitation/Article/ArticleTitle"))
        if not pmid or not pmid.isdecimal():
            invalid.append(InvalidPubMedRecord(pmid, "Missing or invalid PMID"))
            continue
        if not title:
            invalid.append(InvalidPubMedRecord(pmid, "Missing article title"))
            continue
        journal = _text(article.find("./MedlineCitation/Article/Journal/Title"))
        if not journal:
            journal = _text(article.find("./MedlineCitation/Article/Journal/ISOAbbreviation"))
        documents.append(BiomedicalDocument(
            source="pubmed",
            source_id=pmid,
            title=title,
            abstract=_abstract(article),
            authors=_authors(article),
            journal=journal,
            doi=_doi(article),
            publication_year=_year(article),
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        ))
    return ParsedPubMedBatch(documents, invalid)


def parse_esearch_xml(xml: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise PubMedParseError("Malformed ESearch XML") from exc
    if root.tag != "eSearchResult" or root.find("ERROR") is not None or root.find("ErrorList") is not None:
        raise PubMedParseError("Unexpected ESearch response")
    id_list = root.find("IdList")
    if id_list is None:
        raise PubMedParseError("ESearch response lacks IdList")
    ids = [_text(item) for item in id_list.findall("Id")]
    if any(pmid is None or not pmid.isdecimal() for pmid in ids):
        raise PubMedParseError("ESearch returned an invalid PMID")
    return [pmid for pmid in ids if pmid is not None]
