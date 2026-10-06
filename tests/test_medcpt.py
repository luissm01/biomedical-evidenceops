"""Adapter checks with fake libraries: no model downloads or inference."""
from contextlib import nullcontext
from dataclasses import asdict
from types import SimpleNamespace
import sys
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import pytest

from evidenceops.chunking import build_retrievable_unit
from evidenceops.biomedical import BiomedicalDocument
from evidenceops.embeddings import LocalMedCPT, EmbeddingCompatibilityError


@pytest.fixture
def libraries(monkeypatch):
    output = MagicMock()
    output.last_hidden_state.__getitem__ = Mock(return_value=output)
    output.__getitem__.return_value = output
    output.tolist.return_value = [2.0] * 768
    model = Mock(return_value=output)
    model.to.return_value = model
    model.eval.return_value = model
    model.config.hidden_size = 768
    tokenizer = Mock(return_value={"input_ids": SimpleNamespace(shape=(1, 10))})
    model_loader, tokenizer_loader = Mock(return_value=model), Mock(return_value=tokenizer)
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        AutoModel=SimpleNamespace(from_pretrained=model_loader),
        AutoTokenizer=SimpleNamespace(from_pretrained=tokenizer_loader),
    ))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    return tokenizer, model, model_loader, tokenizer_loader


def test_lazy_load_pinned_pair_cls_cpu_and_reuse(libraries):
    tokenizer, model, model_loader, tokenizer_loader = libraries
    encoder = LocalMedCPT()
    assert model_loader.call_count == 0
    unit = build_retrievable_unit(BiomedicalDocument(source="pubmed", source_id="1", title="Title", abstract="Abstract", authors=[], journal=None, doi=None, publication_year=2024, source_url=None), publication_id=uuid4())
    assert encoder.encode_article(unit) == [2.0] * 768
    model.return_value.last_hidden_state.__getitem__.assert_called_once_with((slice(None), 0, slice(None)))
    model.return_value.__getitem__.assert_called_once_with(0)
    tokenizer.assert_called_with([["Title", "Abstract"]], truncation=True, max_length=512, padding=True, return_tensors="pt")
    model_loader.assert_called_with(encoder.config.article_model, revision=encoder.config.article_revision)
    encoder.encode_article(unit)
    assert model_loader.call_count == 1
    encoder.encode_query("  query  ")
    tokenizer.assert_called_with(["query"], truncation=True, max_length=64, padding=True, return_tensors="pt")
    model_loader.assert_called_with(encoder.config.query_model, revision=encoder.config.query_revision)
    assert model_loader.call_count == tokenizer_loader.call_count == 2
    model.to.assert_called_with("cpu")
    model.eval.assert_called()


@pytest.mark.parametrize("kind,limit", [("query", 64), ("article", 512)])
def test_long_input_is_encoded_with_truncation(libraries, kind, limit):
    tokenizer, model, *_ = libraries
    encoder = LocalMedCPT()
    long_text = "biomedical " * (limit + 100)
    # Simulate the tokenizer's bounded tensor, without running real libraries.
    encoded = {"input_ids": SimpleNamespace(shape=(1, limit))}
    tokenizer.return_value = encoded
    if kind == "article":
        unit = build_retrievable_unit(BiomedicalDocument(
            source="pubmed", source_id="1", title="Title", abstract=long_text,
            authors=["Author"], journal="Journal", doi="10.1/example",
            publication_year=2024, source_url="https://pubmed.ncbi.nlm.nih.gov/1/",
        ), publication_id=uuid4())
        original = asdict(unit)
        vector = encoder.encode_article(unit)
        assert asdict(unit) == original
        assert unit.text == "Title\n\n" + long_text
        texts = [["Title", long_text]]
    else:
        vector = encoder.encode_query(long_text)
        texts = [long_text.strip()]
    tokenizer.assert_called_once_with(
        texts, truncation=True, max_length=limit, padding=True, return_tensors="pt",
    )
    model.assert_called_once_with(**encoded)
    assert vector == [2.0] * 768
    assert encoder.config.metadata()["overflow"] == "truncate-longest-first"
    assert encoder.config.metadata()[f"{kind}_max_tokens"] == limit


def test_hidden_dimension_rejected(libraries):
    _, model, *_ = libraries
    model.config.hidden_size = 2
    with pytest.raises(EmbeddingCompatibilityError):
        LocalMedCPT().encode_query("query")
