from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from evidenceops.config import PubMedSettings
from evidenceops.pubmed import PubMedClient, PubMedError, PubMedErrorCause
from evidenceops.pubmed_parser import PubMedParseError, parse_pubmed_xml


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parses_metadata_multisection_abstract_and_authors() -> None:
    parsed = parse_pubmed_xml(fixture("pubmed_articles.xml"))

    assert parsed.invalid_records == []
    first, second = parsed.documents
    assert (first.source, first.source_id, first.title) == (
        "pubmed", "12345", "Effect of treatment in adults."
    )
    assert first.abstract == "BACKGROUND: Clinical context.\nMETHODS: A randomized trial.\nRESULTS: Improved outcomes."
    assert first.authors == ["Ana María García", "Evidence Study Group", "J Lee Jr"]
    assert (first.journal, first.doi, first.publication_year) == (
        "Journal of Evidence", "10.1234/example", 2024
    )
    assert first.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert second.abstract is None
    assert second.authors == []
    assert (second.journal, second.doi, second.publication_year) == ("J Evid", None, 2021)


def test_missing_optional_fields_and_article_date_fallback() -> None:
    xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>
    <Article><ArticleTitle>Short report</ArticleTitle><ArticleDate><Year>2020</Year></ArticleDate>
    <ELocationID EIdType="doi">10.1/fallback</ELocationID></Article></MedlineCitation>
    </PubmedArticle></PubmedArticleSet>"""
    doc = parse_pubmed_xml(xml).documents[0]
    assert (doc.abstract, doc.authors, doc.journal) == (None, [], None)
    assert (doc.doi, doc.publication_year) == ("10.1/fallback", 2020)


def test_partial_invalid_records_are_reported() -> None:
    parsed = parse_pubmed_xml(fixture("pubmed_partial.xml"))
    assert [doc.source_id for doc in parsed.documents] == ["12345"]
    assert [(item.source_id, item.reason) for item in parsed.invalid_records] == [
        ("67890", "Missing article title"), (None, "Missing or invalid PMID")
    ]


@pytest.mark.parametrize("xml", [b"<broken", b"<html></html>", b"<PubmedArticleSet><ERROR>bad</ERROR></PubmedArticleSet>"])
def test_invalid_xml_envelope_raises(xml: bytes) -> None:
    with pytest.raises(PubMedParseError):
        parse_pubmed_xml(xml)


def test_search_and_fetch_use_eutilities_and_optional_identity() -> None:
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("esearch.fcgi"):
            return httpx.Response(200, content=b"<eSearchResult><IdList><Id>12345</Id><Id>67890</Id></IdList></eSearchResult>")
        return httpx.Response(200, content=fixture("pubmed_articles.xml"))

    transport = httpx.MockTransport(respond)
    with httpx.Client(transport=transport) as http_client:
        client = PubMedClient(PubMedSettings(api_key="test-key", email="dev@example.org", _env_file=None), http_client=http_client, sleep=lambda _: None)
        assert client.search("test query", limit=2) == ["12345", "67890"]
        result = client.fetch(["12345", "67890", "12345"])

    assert [doc.source_id for doc in result.documents] == ["12345", "67890"]
    assert result.invalid_records == []
    assert calls[0].method == "GET" and calls[1].method == "POST"
    assert calls[0].url.params["retmax"] == "2"
    assert calls[0].url.params["term"] == "test query"
    assert b"id=12345%2C67890" in calls[1].content
    assert b"api_key=test-key" in calls[1].content
    assert b"email=dev%40example.org" in calls[1].content


def test_fetch_reports_invalid_and_missing_pmids() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=fixture("pubmed_partial.xml")))
    with httpx.Client(transport=transport) as http_client:
        result = PubMedClient(PubMedSettings(_env_file=None), http_client=http_client).fetch(["12345", "67890", "99999"])
    assert [doc.source_id for doc in result.documents] == ["12345"]
    assert [(item.source_id, item.reason) for item in result.invalid_records] == [
        ("67890", "Missing article title"),
        (None, "Missing or invalid PMID"),
        ("99999", "PMID absent from EFetch response"),
    ]


def test_fetch_batches_at_200() -> None:
    sizes: list[int] = []

    def respond(request: httpx.Request) -> httpx.Response:
        import urllib.parse
        ids = urllib.parse.parse_qs(request.content.decode())["id"][0].split(",")
        sizes.append(len(ids))
        articles = "".join(f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>T</ArticleTitle></Article></MedlineCitation></PubmedArticle>" for pmid in ids)
        return httpx.Response(200, content=f"<PubmedArticleSet>{articles}</PubmedArticleSet>".encode())

    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        result = PubMedClient(PubMedSettings(_env_file=None), http_client=http_client, sleep=lambda _: None).fetch(map(str, range(1, 202)))
    assert sizes == [200, 1]
    assert len(result.documents) == 201


@pytest.mark.parametrize("status,cause", [(429, PubMedErrorCause.RATE_LIMIT), (503, PubMedErrorCause.HTTP_ERROR)])
def test_http_errors_are_classified(status: int, cause: PubMedErrorCause) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status))) as http_client:
        with pytest.raises(PubMedError) as error:
            PubMedClient(PubMedSettings(_env_file=None), http_client=http_client).search("query", limit=1)
    assert error.value.cause == cause


def test_timeout_is_classified_without_retry() -> None:
    calls = 0

    def timeout(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as http_client:
        with pytest.raises(PubMedError) as error:
            PubMedClient(PubMedSettings(_env_file=None), http_client=http_client).search("query", limit=1)
    assert error.value.cause == PubMedErrorCause.TIMEOUT
    assert calls == 1


def test_ncbi_json_rate_limit_is_classified() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"error": "API rate limit exceeded"}))) as http_client:
        with pytest.raises(PubMedError) as error:
            PubMedClient(PubMedSettings(_env_file=None), http_client=http_client).search("query", limit=1)
    assert error.value.cause == PubMedErrorCause.RATE_LIMIT


def test_unexpected_or_duplicate_efetch_ids_fail_batch() -> None:
    for ids in [["2"], ["1", "1"]]:
        articles = "".join(f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article><ArticleTitle>T</ArticleTitle></Article></MedlineCitation></PubmedArticle>" for pmid in ids)
        with httpx.Client(transport=httpx.MockTransport(lambda _, articles=articles: httpx.Response(200, content=f"<PubmedArticleSet>{articles}</PubmedArticleSet>".encode()))) as http_client:
            with pytest.raises(PubMedError) as error:
                PubMedClient(PubMedSettings(_env_file=None), http_client=http_client).fetch(["1"])
        assert error.value.cause == PubMedErrorCause.INVALID_RESPONSE


def test_request_spacing_without_api_key() -> None:
    now = 10.0
    waits: list[float] = []

    def advance(delay: float) -> None:
        nonlocal now
        waits.append(delay)
        now += delay

    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"<eSearchResult><IdList /></eSearchResult>"))) as http_client:
        client = PubMedClient(PubMedSettings(_env_file=None), http_client=http_client, sleep=advance, monotonic=lambda: now)
        client.search("one", limit=1)
        client.search("two", limit=1)
    assert waits == [pytest.approx(1 / 3)]


@pytest.mark.parametrize("xml", [b"not xml", b"<eSearchResult><ERROR>bad</ERROR></eSearchResult>", b"<eSearchResult><IdList><Id>bad</Id></IdList></eSearchResult>"])
def test_bad_search_response_is_classified(xml: bytes) -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=xml))) as http_client:
        with pytest.raises(PubMedError) as error:
            PubMedClient(PubMedSettings(_env_file=None), http_client=http_client).search("query", limit=1)
    assert error.value.cause == PubMedErrorCause.INVALID_RESPONSE


def test_invalid_inputs_make_no_request() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("unexpected request"))) as http_client:
        client = PubMedClient(PubMedSettings(_env_file=None), http_client=http_client)
        for query, limit in [("", 1), ("valid", 0), ("valid", 101)]:
            with pytest.raises(ValueError):
                client.search(query, limit=limit)
        with pytest.raises(ValueError):
            client.fetch(["1", "bad"])
        assert client.fetch([]).documents == []


def test_pubmed_settings_are_independent_and_validate() -> None:
    settings = PubMedSettings(api_key="", email="", _env_file=None)
    assert settings.api_key is None and settings.email is None
    with pytest.raises(ValidationError):
        PubMedSettings(timeout_seconds=0, _env_file=None)
    with pytest.raises(ValidationError):
        PubMedSettings(email="invalid", _env_file=None)
