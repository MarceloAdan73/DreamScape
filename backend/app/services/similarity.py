"""Índice de similitud sobre ChromaDB (persistente, en disco, sin servicios externos).

ChromaDB embebido corre en el mismo proceso y guarda en `data/chroma/`.
Las operaciones de Chroma son síncronas/bloqueantes; se ejecutan en un thread
del pool para no bloquear el event loop (decisión documentada en el README).

Métrica: espacio `cosine`, distancia ∈ [0, 2]. `similarity = 1 - distancia`.
El umbral configura la distancia MÁXIMA aceptada (`similarity_threshold`).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from typing import Any, cast

import chromadb

from app.core.config import Settings
from app.core.llm import LLMProvider


@dataclass(frozen=True)
class SimilarCandidate:
    """Un sueño similar al consultado, con su score de similitud 0-1."""

    dream_id: int
    similarity: float


class SimilarityIndex:
    """Embebe, indexa y consulta sueños similares en ChromaDB."""

    def __init__(self, settings: Settings) -> None:
        if settings.chroma_path:
            os.makedirs(settings.chroma_path, exist_ok=True)
        self._client = chromadb.PersistentClient(path=settings.chroma_path)
        self._collection_name = settings.chroma_collection
        self._collection = self._client.get_or_create_collection(
            self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _search_sync(
        self,
        embedding: list[float],
        dream_id: int,
        top_k: int,
        threshold: float,
    ) -> list[SimilarCandidate]:
        count = self._collection.count()
        if count == 0:
            return []
        n_results = max(1, min(count, top_k))
        result = self._collection.query(
            query_embeddings=cast(Any, [embedding]),
            n_results=n_results,
            where=cast(Any, {"dream_id": {"$ne": dream_id}}),
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        candidates: list[SimilarCandidate] = []
        for doc_id, distance in zip(ids, distances, strict=False):
            if distance <= threshold:
                try:
                    other_id = int(doc_id)
                except (TypeError, ValueError):
                    continue
                candidates.append(SimilarCandidate(other_id, round(1.0 - distance, 4)))
        return candidates

    def _store_sync(self, text: str, embedding: list[float], dream_id: int) -> None:
        self._collection.upsert(
            ids=[str(dream_id)],
            embeddings=cast(Any, [embedding]),
            metadatas=cast(Any, [{"dream_id": dream_id, "preview": text[:200]}]),
            documents=[text],
        )

    async def index_and_search(
        self,
        provider: LLMProvider,
        text: str,
        dream_id: int,
        top_k: int,
        threshold: float,
    ) -> list[SimilarCandidate]:
        """Embede el texto, busca los más similares y lo indexa (todo en threads)."""
        embedding = (await provider.embed([text]))[0]
        candidates = await asyncio.to_thread(
            self._search_sync, embedding, dream_id, top_k, threshold
        )
        await asyncio.to_thread(self._store_sync, text, embedding, dream_id)
        return candidates

    def _clear_sync(self) -> None:
        """Borra la colección completa y la recrea vacía."""
        # Si la colección no existe, no hay nada que borrar.
        with contextlib.suppress(Exception):
            self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def clear(self) -> None:
        """Vacía el índice de similitud (usado por el reinicio total)."""
        await asyncio.to_thread(self._clear_sync)
