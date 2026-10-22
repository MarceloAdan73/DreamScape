"""Esquemas de la capa de análisis: grafo de sueños y patrones (Fase 3).

El grafo alimenta la visualización 3D del frontend (react-three-fiber):
nodos = sueños, aristas = `DreamLink` con su similitud. La detección de
patrones devuelve las entidades recurrentes entre sueños analizados.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.dream import EntityType


class GraphNode(BaseModel):
    """Nodo del grafo 3D: un sueño."""

    id: int
    title: str | None = None
    preview: str = Field(description="Primeros caracteres del relato.")
    analysis_status: str
    insight: str | None = None
    mood_on_wake: str | None = None
    dreamed_at: date | None = None
    created_at: datetime


class GraphEdge(BaseModel):
    """Arista del grafo 3D: dos sueños similares."""

    source: int
    target: int
    similarity: float


class GraphPayload(BaseModel):
    """Payload completo del grafo de conexiones entre sueños."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Pattern(BaseModel):
    """Entidad recurrente detectada entre los sueños."""

    name: str
    type: EntityType
    dream_count: int
    last_seen_at: datetime | None = None
    exemplar_dream_id: int | None = None
    interpretation: str | None = None


class PatternsResponse(BaseModel):
    """Resultado del detector de patrones."""

    dreams_analyzed: int
    total: int
    patterns: list[Pattern]


class ReadingResponse(BaseModel):
    """Lectura narrativa generada a partir de los patrones recurrentes."""

    reading: str | None = None
    detail: str | None = None