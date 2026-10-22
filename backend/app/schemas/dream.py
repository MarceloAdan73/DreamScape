"""Esquemas Pydantic v2 para sueños y su análisis.

`DreamAnalysis` es el contrato que DEBE cumplir la salida del LLM (Fase 2).
Se define aquí, junto a los demás esquemas, para que el extractor y los
endpoints compartan una única fuente de verdad.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AnalysisStatus = Literal["pending", "processing", "completed", "failed"]
EntityType = Literal["symbol", "emotion", "person", "place"]


class DreamBase(BaseModel):
    """Campos comunes de entrada/salida de un sueño."""

    text: str = Field(min_length=1, max_length=20_000, description="Relato del sueño.")
    mood_on_wake: str | None = Field(
        default=None, max_length=32, description="Ánimo al despertar (opcional)."
    )
    dreamed_at: date | None = Field(default=None, description="Fecha en que se soñó.")

    @field_validator("text")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("El texto del sueño no puede estar vacío.")
        return cleaned

    @field_validator("mood_on_wake")
    @classmethod
    def _clean_mood(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DreamCreate(DreamBase):
    """Payload de `POST /api/dreams`."""


class DreamRead(DreamBase):
    """Representación de un sueño devuelta por la API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None = None
    analysis_status: AnalysisStatus
    one_line_insight: str | None = None
    summary: str | None = None
    analysis_error: str | None = None
    created_at: datetime
    analyzed_at: datetime | None = None


class DreamList(BaseModel):
    """Lista paginada de sueños."""

    total: int
    items: list[DreamRead]


# --- Contrato de análisis (salida del LLM) ---------------------------------


class SymbolOut(BaseModel):
    """Símbolo onírico con interpretación junguiana breve."""

    name: str = Field(min_length=1, max_length=120)
    interpretation: str = Field(min_length=1, max_length=600)


class EmotionOut(BaseModel):
    """Emoción detectada con intensidad 0-10."""

    name: str = Field(min_length=1, max_length=60)
    score: float = Field(ge=0, le=10)


class DreamAnalysis(BaseModel):
    """Salida estructurada que el extractor exige al LLM."""

    title: str = Field(min_length=1, max_length=90)
    symbols: list[SymbolOut] = Field(default_factory=list)
    emotions: list[EmotionOut] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    one_line_insight: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=2000)
