"""Embeddings multilingues sur CPU et similarité offre / CV (SPEC §3.4)."""
import hashlib
import math
import os
import re
from typing import Protocol

from db.models import EMBEDDING_DIM

MODEL_NAME = "intfloat/multilingual-e5-base"
OFFER_CHARS = 1500


class Embedder(Protocol):
    def embed_cvs(self, texts: list[str]) -> list[list[float]]: ...
    def embed_offers(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """e5 demande un préfixe : « passage: » pour les deux côtés (comparaison symétrique texte à texte)."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        from sentence_transformers import SentenceTransformer  # extra « embeddings » (image Docker)

        self._model = SentenceTransformer(model_name, device="cpu")

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            [f"passage: {t}" for t in texts], normalize_embeddings=True, batch_size=16)
        return [[float(x) for x in v] for v in vectors]

    embed_cvs = _encode
    embed_offers = _encode


class FakeEmbedder:
    """Sac de mots haché, déterministe : pour les tests, sans modèle ni réseau."""

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"\w+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_cvs(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    embed_offers = embed_cvs


def get_embedder() -> Embedder:
    name = os.environ.get("EMBEDDING_MODEL", MODEL_NAME)
    return FakeEmbedder() if name == "fake" else SentenceTransformerEmbedder(name)


def offer_text(title: str, organization: str | None, description: str | None) -> str:
    parts = [title, organization or "", (description or "")[:OFFER_CHARS]]
    return re.sub(r"\s+", " ", " . ".join(p for p in parts if p)).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def best_cv(vector: list[float], cvs: dict[str, list[float]]) -> tuple[str, float] | None:
    """(code du CV le plus proche, similarité cosinus) ; None sans CV."""
    scored = [(code, cosine(vector, v)) for code, v in cvs.items()]
    return max(scored, key=lambda t: t[1]) if scored else None
