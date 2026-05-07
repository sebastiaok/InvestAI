from __future__ import annotations

import hashlib
from typing import List

from app.config import OPENAI_EMBED_MODEL
from app.services.llm import client


class OpenAIClientEmbeddings:
    def __init__(self, model: str = OPENAI_EMBED_MODEL):
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            response = client.embeddings.create(model=self.model, input=texts)
            return [row.embedding for row in response.data]
        except Exception:
            return [self._fallback_embedding(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        try:
            response = client.embeddings.create(model=self.model, input=[text])
            return response.data[0].embedding
        except Exception:
            return self._fallback_embedding(text)

    def __call__(self, text: str) -> List[float]:
        return self.embed_query(text)

    def _fallback_embedding(self, text: str, dim: int = 256) -> List[float]:
        # deterministic offline embedding fallback for local indexing/testing
        values: List[float] = []
        seed = text.encode("utf-8")
        nonce = 0
        while len(values) < dim:
            digest = hashlib.sha256(seed + nonce.to_bytes(4, "big")).digest()
            for byte in digest:
                values.append((byte / 255.0) * 2.0 - 1.0)
                if len(values) >= dim:
                    break
            nonce += 1
        return values


def build_embeddings():
    return OpenAIClientEmbeddings(model=OPENAI_EMBED_MODEL)
