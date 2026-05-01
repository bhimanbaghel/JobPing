"""Text-embedding service for the recommendation pipeline.

Two backends are supported:

- ``sbert`` (default): the local ``sentence-transformers/all-MiniLM-L6-v2``
  model. Loaded lazily and cached as a module-level singleton so the
  ~90 MB weight load happens at most once per process.

- ``hashing``: a deterministic hashing fallback used by tests and any
  environment without network access. It produces L2-normalized 384-dim
  vectors so the recommender's cosine math still works end-to-end.

Select the backend at runtime via the ``EMBEDDING_BACKEND`` env var.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Iterable, List

import numpy as np

from app.models import EMBEDDING_DIM, JobEmbedding, ResumeEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CACHE_DIR = (
    Path(__file__).resolve().parents[2] / ".cache" / "sentence_transformers"
)

_model = None


def _backend() -> str:
    return os.environ.get("EMBEDDING_BACKEND", "sbert").strip().lower()


def get_model():
    """Return (and cache) the SentenceTransformer model."""
    global _model
    if _model is None:
        cache_dir = Path(
            os.environ.get("SENTENCE_TRANSFORMERS_HOME", str(DEFAULT_CACHE_DIR))
        )
        cache_dir.mkdir(parents=True, exist_ok=True)

        from sentence_transformers import SentenceTransformer  # heavy import
        _model = SentenceTransformer(MODEL_NAME, cache_folder=str(cache_dir))
    return _model


def warmup_model() -> bool:
    """Load SBERT once at startup and keep weights cached on disk."""
    if _backend() != "sbert":
        return False
    get_model()
    return True


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _hashing_embed(text: str) -> np.ndarray:
    """Token-hashing embedding used when the SBERT backend is unavailable.

    Each token contributes ``+1`` or ``-1`` to a fixed slot determined by
    its SHA1, and the final vector is L2-normalized. This is deterministic,
    fast, and good enough to exercise the recommender end-to-end in tests.
    """
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    for token in _TOKEN_RE.findall(text.lower()):
        h = int(hashlib.sha1(token.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBEDDING_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        vec /= norm
    return vec


def embed_texts(texts: Iterable[str]) -> List[List[float]]:
    """Embed a batch of strings into L2-normalized 384-dim vectors."""
    items = [(t or "").strip() for t in texts]
    if not items:
        return []

    if _backend() == "hashing":
        arr = np.stack([_hashing_embed(t) for t in items])
    else:
        model = get_model()
        arr = model.encode(
            items,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        arr = np.asarray(arr, dtype=np.float32)
    return [row.tolist() for row in arr]


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]


def upsert_job_embedding(session, job_id: int, description: str) -> JobEmbedding:
    """Compute and store the vector for a job description."""
    vec = embed_text(description)
    obj = session.get(JobEmbedding, job_id)
    if obj is None:
        obj = JobEmbedding(job_id=job_id, embedding=vec)
        session.add(obj)
    else:
        obj.embedding = vec
    return obj


def upsert_resume_embedding(
    session, user_id: int, text: str, source: str = "resume"
) -> ResumeEmbedding:
    """Compute and store the vector for a user's resume or preference query.

    ``source`` is ``'resume'`` when ``text`` came from the uploaded resume,
    or ``'preferences'`` when it was synthesized from the user's preferred
    roles/companies/locations (FR6.3 fallback).
    """
    if source not in {"resume", "preferences"}:
        raise ValueError(f"invalid source: {source!r}")
    vec = embed_text(text)
    obj = session.get(ResumeEmbedding, user_id)
    if obj is None:
        obj = ResumeEmbedding(user_id=user_id, embedding=vec, source=source)
        session.add(obj)
    else:
        obj.embedding = vec
        obj.source = source
    return obj
