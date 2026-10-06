"""Small MedCPT boundary; importing this module never loads model libraries."""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Protocol

from evidenceops.chunking import CHUNKING_STRATEGY, RetrievableUnit

DIMENSIONS = 768


class EmbeddingCompatibilityError(ValueError):
    """Representation does not match the requested MedCPT configuration."""


@dataclass(frozen=True, slots=True)
class MedCPTConfig:
    article_model: str = "ncbi/MedCPT-Article-Encoder"
    article_revision: str = "d05a736da4bb84ee4057b7f7999485be6ed85465"
    query_model: str = "ncbi/MedCPT-Query-Encoder"
    query_revision: str = "d83a36cc6b8e3a5c5e9d9d6ba156808c1643dcbc"
    dimensions: int = DIMENSIONS
    strategy: str = CHUNKING_STRATEGY
    encoding: str = "medcpt-title-abstract-pair-cls-v1"
    article_max_tokens: int = 512
    query_max_tokens: int = 64
    overflow: str = "truncate-longest-first"
    normalization: str = "none"
    similarity: str = "inner-product"

    def metadata(self) -> dict:
        return asdict(self)


def validate_vector(vector: list[float]) -> list[float]:
    if len(vector) != DIMENSIONS:
        raise EmbeddingCompatibilityError(f"Expected {DIMENSIONS} dimensions, got {len(vector)}")
    # PostgreSQL vector stores float32, so reject overflow before persistence.
    if any(not isfinite(value) or abs(value) > 3.4028234663852886e38 for value in vector):
        raise ValueError("Embedding must contain finite float32 values")
    return vector


def validate_config(config: MedCPTConfig) -> None:
    if config.dimensions != DIMENSIONS or config.strategy != CHUNKING_STRATEGY:
        raise EmbeddingCompatibilityError("Unsupported dimensions or unit strategy")


def article_inputs(title: str, abstract: str | None) -> tuple[str, str]:
    """Exact pair sent to the Article Encoder; blank fields encode as empty."""
    return (title if title.strip() else "", abstract if abstract and abstract.strip() else "")


class MedCPTEncoder(Protocol):
    """Test seam for this single local model, not a provider selection layer."""

    config: MedCPTConfig

    def encode_article(self, unit: RetrievableUnit) -> list[float]: ...

    def encode_query(self, query: str) -> list[float]: ...


class LocalMedCPT:
    config = MedCPTConfig()

    def __init__(self) -> None:
        self._encoders: dict = {}

    def _load(self, kind: str):
        if kind not in self._encoders:
            try:
                from transformers import AutoModel, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError("Install the medcpt extra: uv sync --extra medcpt") from exc
            model_id = getattr(self.config, f"{kind}_model")
            revision = getattr(self.config, f"{kind}_revision")
            tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
            model = AutoModel.from_pretrained(model_id, revision=revision).to("cpu").eval()
            if model.config.hidden_size != DIMENSIONS:
                raise EmbeddingCompatibilityError("MedCPT hidden size differs from schema")
            self._encoders[kind] = tokenizer, model
        return self._encoders[kind]

    def _encode(self, kind: str, texts: list) -> list[float]:
        tokenizer, model = self._load(kind)
        import torch
        encoded = tokenizer(
            texts, truncation=True,
            max_length=getattr(self.config, f"{kind}_max_tokens"),
            padding=True, return_tensors="pt",
        )
        with torch.inference_mode():
            vector = model(**encoded).last_hidden_state[:, 0, :][0].tolist()
        return validate_vector(vector)

    def encode_article(self, unit: RetrievableUnit) -> list[float]:
        if unit.strategy != self.config.strategy:
            raise EmbeddingCompatibilityError("Unsupported unit strategy")
        return self._encode("article", [list(article_inputs(unit.title, unit.abstract))])

    def encode_query(self, query: str) -> list[float]:
        if not query.strip():
            raise ValueError("Query must contain text")
        return self._encode("query", [query.strip()])
