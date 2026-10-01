"""Small synchronous NCBI E-utilities client for explicit PMID acquisition."""

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock

import httpx

from evidenceops.biomedical import BiomedicalDocument
from evidenceops.config import PubMedSettings
from evidenceops.pubmed_parser import (
    InvalidPubMedRecord,
    PubMedParseError,
    parse_esearch_xml,
    parse_pubmed_xml,
)


_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_BATCH_SIZE = 200
_MAX_SEARCH_RESULTS = 100


class PubMedErrorCause(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    HTTP_ERROR = "http_error"
    TRANSPORT = "transport"
    INVALID_RESPONSE = "invalid_response"


class PubMedError(Exception):
    def __init__(self, cause: PubMedErrorCause, message: str) -> None:
        self.cause = cause
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PubMedFetchResult:
    documents: list[BiomedicalDocument]
    invalid_records: list[InvalidPubMedRecord]


class PubMedClient:
    def __init__(
        self,
        settings: PubMedSettings | None = None,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings or PubMedSettings()
        self._client = http_client or httpx.Client(timeout=self._settings.timeout_seconds)
        self._owns_client = http_client is None
        self._sleep = sleep
        self._monotonic = monotonic
        self._next_request_at = 0.0
        self._rate_lock = Lock()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PubMedClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _request(self, endpoint: str, parameters: dict[str, str], *, post: bool = False) -> bytes:
        params = {"db": "pubmed", "tool": self._settings.tool, **parameters}
        if self._settings.email:
            params["email"] = self._settings.email
        if self._settings.api_key:
            params["api_key"] = self._settings.api_key.get_secret_value()

        # Serialize request starts for this client. NCBI counts requests per IP;
        # callers sharing an IP must coordinate other clients themselves.
        interval = 0.1 if self._settings.api_key else 1 / 3
        with self._rate_lock:
            delay = self._next_request_at - self._monotonic()
            if delay > 0:
                self._sleep(delay)
            self._next_request_at = self._monotonic() + interval

        try:
            url = _BASE_URL + endpoint
            response = (
                self._client.post(url, data=params, timeout=self._settings.timeout_seconds)
                if post else self._client.get(url, params=params, timeout=self._settings.timeout_seconds)
            )
            response.raise_for_status()
            if response.content.lstrip().startswith(b"{"):
                try:
                    payload = json.loads(response.content)
                except (ValueError, UnicodeError):
                    payload = None
                if isinstance(payload, dict) and isinstance(payload.get("error"), str) and "rate limit" in payload["error"].lower():
                    raise PubMedError(PubMedErrorCause.RATE_LIMIT, "PubMed rate limit was reached")
            return response.content
        except httpx.TimeoutException as exc:
            raise PubMedError(PubMedErrorCause.TIMEOUT, "PubMed request timed out") from exc
        except httpx.HTTPStatusError as exc:
            cause = PubMedErrorCause.RATE_LIMIT if exc.response.status_code == 429 else PubMedErrorCause.HTTP_ERROR
            raise PubMedError(cause, f"PubMed returned HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise PubMedError(PubMedErrorCause.TRANSPORT, "PubMed request failed") from exc

    def search(self, query: str, *, limit: int) -> list[str]:
        """Return at most `limit` PMIDs; search is discovery, not retrieval."""
        if not query.strip():
            raise ValueError("PubMed query must not be empty")
        if not 1 <= limit <= _MAX_SEARCH_RESULTS:
            raise ValueError(f"PubMed search limit must be between 1 and {_MAX_SEARCH_RESULTS}")
        xml = self._request("esearch.fcgi", {
            "term": query.strip(), "retmax": str(limit), "retmode": "xml",
        })
        try:
            ids = parse_esearch_xml(xml)
        except PubMedParseError as exc:
            raise PubMedError(PubMedErrorCause.INVALID_RESPONSE, str(exc)) from exc
        if len(ids) > limit:
            raise PubMedError(PubMedErrorCause.INVALID_RESPONSE, "ESearch exceeded the requested limit")
        return ids

    def fetch(self, pmids: Iterable[str]) -> PubMedFetchResult:
        """Fetch explicit PMIDs in batches; one external batch may fail as a unit."""
        ids = list(dict.fromkeys(pmids))
        if any(not isinstance(pmid, str) or not pmid.isdecimal() for pmid in ids):
            raise ValueError("PMIDs must be nonempty decimal strings")
        documents: list[BiomedicalDocument] = []
        invalid: list[InvalidPubMedRecord] = []
        for offset in range(0, len(ids), _BATCH_SIZE):
            batch = ids[offset:offset + _BATCH_SIZE]
            xml = self._request("efetch.fcgi", {
                "id": ",".join(batch), "retmode": "xml",
            }, post=True)
            try:
                parsed = parse_pubmed_xml(xml)
            except PubMedParseError as exc:
                raise PubMedError(PubMedErrorCause.INVALID_RESPONSE, str(exc)) from exc
            requested = set(batch)
            returned = {doc.source_id for doc in parsed.documents}
            returned.update(item.source_id for item in parsed.invalid_records if item.source_id)
            if not returned <= requested or len(returned) != len(parsed.documents) + sum(
                item.source_id is not None for item in parsed.invalid_records
            ):
                raise PubMedError(PubMedErrorCause.INVALID_RESPONSE, "EFetch returned unexpected or duplicate PMIDs")
            documents.extend(parsed.documents)
            invalid.extend(parsed.invalid_records)
            invalid.extend(InvalidPubMedRecord(pmid, "PMID absent from EFetch response") for pmid in batch if pmid not in returned)
        return PubMedFetchResult(documents, invalid)
