"""Fakes del proveedor de IA para tests (misma interfaz que LLMProvider)."""

from __future__ import annotations

import json

DEFAULT_ANALYSIS_JSON = json.dumps(
    {
        "title": "El océano que guardaba la memoria",
        "symbols": [
            {"name": "océano", "interpretation": "El océano es el inconsciente extendido."}
        ],
        "emotions": [{"name": "asombro", "score": 8.0}],
        "people": ["mamá"],
        "places": ["la ciudad de cristal"],
        "one_line_insight": "La tinta es la memoria sin nombrar.",
        "summary": "El sueño te muestra una superficie en calma que esconde profundidad.",
    }
)

# JSON parseable pero con el schema inválido (falta "summary").
INVALID_SCHEMA_JSON = json.dumps(
    {
        "symbols": [{"name": "océano", "interpretation": "Profundo."}],
        "emotions": [],
        "people": [],
        "places": [],
        "one_line_insight": "Insight sin summary.",
    }
)


class FakeProvider:
    """Proveedor determinista controlable desde el test."""

    name = "fake"

    def __init__(
        self,
        chat_responses: list[str] | None = None,
        chat_error: Exception | None = None,
    ) -> None:
        self.chat_responses = list(chat_responses) if chat_responses else [DEFAULT_ANALYSIS_JSON]
        self.chat_error = chat_error
        self.chat_calls: list[list[dict[str, str]]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        self.chat_calls.append(messages)
        if self.chat_error is not None:
            raise self.chat_error
        if self.chat_responses:
            return self.chat_responses.pop(0)
        return DEFAULT_ANALYSIS_JSON

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Vector idéntico para todo: dos sueños siempre resultan similares.
        return [[0.5, 0.5, 0.5] for _ in texts]

    async def health(self) -> tuple[bool, str]:
        return (self.chat_error is None, "fake saludable")
