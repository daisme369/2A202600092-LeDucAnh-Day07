from __future__ import annotations

import hashlib
import math
from typing import Iterable

LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_PROVIDER_ENV = "EMBEDDING_PROVIDER"


class MockEmbedder:
    """Deterministic embedding backend used by tests and default classroom runs."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self._backend_name = "mock embeddings fallback"

    def __call__(self, text: str) -> list[float]:
        digest = hashlib.md5(text.encode()).hexdigest()
        seed = int(digest, 16)
        vector = []
        for _ in range(self.dim):
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            vector.append((seed / 0xFFFFFFFF) * 2 - 1)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class LocalEmbedder:
    """Sentence Transformers-backed local embedder."""

    def __init__(self, model_name: str = LOCAL_EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._backend_name = model_name
        self.model = SentenceTransformer(model_name)

    def __call__(self, text: str) -> list[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return [float(value) for value in embedding]


class OpenAIEmbedder:
    """OpenAI embeddings API-backed embedder."""

    def __init__(self, model_name: str = OPENAI_EMBEDDING_MODEL) -> None:
        from openai import OpenAI

        self.model_name = model_name
        self._backend_name = model_name
        self.client = OpenAI()

    def __call__(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model_name, input=text)
        return [float(value) for value in response.data[0].embedding]


class GeminiEmbedder:
    """Google Gemini embedding API-backed embedder with rate limiting + retry."""

    DEFAULT_MODEL = "gemini-embedding-001"
    # Free tier: 100 embed_content requests per minute
    MAX_RPM = 90  # stay well under the 100 limit
    MAX_RETRIES = 5
    BATCH_SIZE = 16

    def __init__(self, api_key: str, model_name: str | None = None) -> None:
        import time

        from google import genai

        self.model_name = model_name or self.DEFAULT_MODEL
        self._backend_name = self.model_name
        self._client = genai.Client(api_key=api_key)
        self._timestamps: list[float] = []
        self._time = time
        self._cache: dict[str, list[float]] = {}

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _throttle(self) -> None:
        """Sleep if we are about to exceed the rate limit."""
        now = self._time.time()
        # Remove timestamps older than 60s
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.MAX_RPM:
            wait = 60 - (now - self._timestamps[0]) + 1.0
            if wait > 0:
                print(f"\r  [RATE LIMIT] Pausing {wait:.0f}s to respect quota...", end="", flush=True)
                self._time.sleep(wait)

    def _embed_request(self, contents: str | list[str]) -> list[list[float]]:
        """Execute one embed_content API call with retries."""
        for attempt in range(self.MAX_RETRIES):
            try:
                self._throttle()
                result = self._client.models.embed_content(
                    model=self.model_name,
                    contents=contents,
                )
                self._timestamps.append(self._time.time())
                return [[float(v) for v in emb.values] for emb in result.embeddings]
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    backoff = min(2 ** attempt * 5, 65)
                    print(
                        f"\r  [RATE LIMIT] 429 received, retrying in {backoff}s "
                        f"(attempt {attempt + 1}/{self.MAX_RETRIES})...",
                        end="",
                        flush=True,
                    )
                    self._time.sleep(backoff)
                else:
                    raise
        raise RuntimeError(f"Failed to embed after {self.MAX_RETRIES} retries")

    def embed_many(self, texts: Iterable[str], batch_size: int | None = None) -> list[list[float]]:
        """Embed many texts with request batching + in-process cache."""
        text_list = list(texts)
        if not text_list:
            return []

        batch_size = max(1, batch_size or self.BATCH_SIZE)
        results: list[list[float] | None] = [None] * len(text_list)

        # Reuse already embedded texts in this run to avoid duplicate API work.
        pending_indices: list[int] = []
        pending_texts: list[str] = []
        for i, text in enumerate(text_list):
            key = self._hash_text(text)
            cached = self._cache.get(key)
            if cached is not None:
                results[i] = cached
            else:
                pending_indices.append(i)
                pending_texts.append(text)

        for start in range(0, len(pending_texts), batch_size):
            batch = pending_texts[start : start + batch_size]
            batch_vecs = self._embed_request(batch)
            for offset, vec in enumerate(batch_vecs):
                idx = pending_indices[start + offset]
                key = self._hash_text(text_list[idx])
                self._cache[key] = vec
                results[idx] = vec

        return [vec for vec in results if vec is not None]

    def __call__(self, text: str) -> list[float]:
        return self.embed_many([text], batch_size=1)[0]


_mock_embed = MockEmbedder()
