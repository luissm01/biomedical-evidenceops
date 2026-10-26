"""One lazy, optional MedCPT Cross-Encoder; scores are raw relevance logits."""

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Protocol

from evidenceops.chunking import RetrievableUnit

RERANK_CANDIDATES = 20


@dataclass(frozen=True, slots=True)
class RerankerConfig:
    model: str = "ncbi/MedCPT-Cross-Encoder"
    revision: str = "71caf65d4927987813984f54c284405a13fcca49"
    max_tokens: int = 512
    text: str = "whole-publication-v1-title-blank-line-abstract"
    truncation: str = "longest_first"
    score: str = "raw-logit-descending"
    device: str = "cpu"
    dtype: str = "float32"
    batch_size: int = 20

    def metadata(self) -> dict:
        return asdict(self)


class MedCPTReranker(Protocol):
    config: RerankerConfig

    def score(self, query: str, units: list[RetrievableUnit]) -> list[float]: ...


def validate_scores(scores: list[float], count: int) -> list[float]:
    if len(scores) != count or any(not isfinite(score) for score in scores):
        raise ValueError("Reranker must return one finite score per candidate")
    return scores


class LocalMedCPTReranker:
    config = RerankerConfig()

    def __init__(self) -> None:
        self._loaded = None

    def _load(self):
        if self._loaded is None:
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError("Install the medcpt extra: uv sync --extra medcpt") from exc
            tokenizer = AutoTokenizer.from_pretrained(self.config.model, revision=self.config.revision)
            model = AutoModelForSequenceClassification.from_pretrained(
                self.config.model, revision=self.config.revision,
            ).to(device="cpu", dtype=torch.float32).eval()
            if model.config.num_labels != 1:
                raise ValueError("MedCPT reranker requires one logit per pair")
            self._loaded = tokenizer, model
        return self._loaded

    def score(self, query: str, units: list[RetrievableUnit]) -> list[float]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must contain text")
        if not units:
            return []
        tokenizer, model = self._load()
        import torch
        scores = []
        for start in range(0, len(units), self.config.batch_size):
            pairs = [[query.strip(), unit.text] for unit in units[start:start + self.config.batch_size]]
            encoded = tokenizer(pairs, truncation=self.config.truncation, max_length=512,
                                padding=True, return_tensors="pt")
            with torch.inference_mode():
                scores.extend(model(**encoded).logits.squeeze(dim=1).tolist())
        return validate_scores(scores, len(units))
