"""Extractor: fuerza al LLM a devolver un `DreamAnalysis` JSON válido.

Dos garantías de calidad:
- El prompt pide explícitamente JSON con un schema fijo (modo `json` del proveedor
  cuando está disponible).
- La salida se valida con Pydantic; si falla, se reenvía al LLM una corrección
  con su propia respuesta (hasta `llm_max_retries` intentos extra).
"""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.core.config import Settings
from app.core.llm import ChatMessage, LLMProvider
from app.schemas.dream import DreamAnalysis

logger = logging.getLogger("dreamscape.extractor")

SYSTEM_PROMPT = """Eres un intérprete de sueños con enfoque junguiano. Analizas el relato
de un sueño y devuelves **únicamente** un objeto JSON válido con esta estructura exacta
(sin markdown, sin texto fuera del JSON):

{
  "title": "título artístico y evocador del sueño",
  "symbols": [
    {"name": "símbolo", "interpretation": "lectura simbólica breve y evocadora"}
  ],
  "emotions": [
    {"name": "emoción", "score": 0.0}
  ],
  "people": ["nombre"],
  "places": ["lugar"],
  "one_line_insight": "una sola línea que ilumine el sueño",
  "summary": "resumen interpretativo de 2 a 4 frases"
}

Reglas:
- "title": entre 3 y 7 palabras, en el idioma del sueño, como un nombre casi
  poético que invite a recordar el sueño sin spoilearlo del todo. DEBE incluir
  al menos 2 palabras clave concretas del relato (objetos, personas, lugares o
  acciones que realmente aparecen), nunca genéricas ni inventadas
  (ej.: para un sueño con "gato", "crías" y "pareja": "El gato y sus crías
  junto a la pareja"). Sin comillas ni punto final.
- "symbols": objetos del sueño con carga simbólica (animales, objetos, agua, etc.),
  con una interpretación en clave junguiana de máximo 2 frases.
- "emotions": emociones explícitas o latentes, cada una con intensidad 0-10.
- "people" y "places": strings simples; listas vacías si no hay.
- Vocabulario canónico: los patrones se detectan comparando nombres exactos
  entre sueños distintos, así que el mismo concepto debe llevar SIEMPRE la misma
  palabra. Si tenés sinónimos ("desesperación" / "desesperanza", "miedo" /
  "angustia"), elegí el más común y neutro, y usá solo ese. No inventes una
  variante nueva si ya hay una palabra sencilla para lo mismo.
- Una palabra por concepto: cada entidad debe ser UNA sola palabra, sin espacios.
  Preferí "presión" sobre "sensación de presión" y "gato" sobre "gato negro".
  Si hace falta una frase, usá solo la palabra principal.
- No repitas el mismo concepto en dos categorías: si algo ya es una persona o
  un lugar, no lo listes además como símbolo.
- "one_line_insight": máximo 300 caracteres, en segunda persona, que resuene.
- "summary": máximo 2000 caracteres, en segunda persona, sin inventar hechos del sueño.
- No inventes símbolos que no estén en el relato.
- Texto y respuestas en el idioma del sueño."""

_CORRECTION = (
    "Tu respuesta anterior no fue un JSON válido para el schema requerido. "
    "Esto fue lo que respondiste:\n{raw}\n"
    "Devuelve únicamente el objeto JSON con el schema exacto especificado, sin markdown."
)


class ExtractionError(RuntimeError):
    """La salida del LLM no se pudo convertir a un `DreamAnalysis` válido."""


def _extract_json_block(raw: str) -> str | None:
    """Aísla el objeto JSON de ruido circundante (fences markdown, prosa)."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


class DreamExtractor:
    """Convierte el relato de un sueño en un `DreamAnalysis` estructurado."""

    def __init__(self, provider: LLMProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    async def extract(
        self, dream_text: str, vocabulary: list[str] | None = None
    ) -> DreamAnalysis:
        system_content = SYSTEM_PROMPT
        if vocabulary:
            terms = ", ".join(sorted({name.strip().lower() for name in vocabulary if name.strip()}))
            if terms:
                system_content = (
                    SYSTEM_PROMPT
                    + "\n\nVocabulario existente (reutiliza estos términos exactos "
                    "cuando aplique, en lugar de inventar variantes nuevas): "
                    + terms
                )
        messages: list[ChatMessage] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": dream_text},
        ]
        max_attempts = 1 + self._settings.llm_max_retries
        for attempt in range(max_attempts):
            last_attempt = attempt == max_attempts - 1
            raw = await self._provider.chat(
                messages,
                json_mode=True,
                temperature=0.4,
            )
            block = _extract_json_block(raw)
            if block is None:
                if last_attempt:
                    raise ExtractionError(
                        f"El LLM no devolvió JSON en {max_attempts} intentos. "
                        f"Respuesta: {raw[:200]}"
                    )
                messages.append({"role": "user", "content": _CORRECTION.format(raw=raw)})
                continue
            try:
                return DreamAnalysis.model_validate_json(block)
            except ValidationError as exc:
                if last_attempt:
                    raise ExtractionError(
                        f"La salida del LLM no cumple el schema tras {max_attempts} intentos: "
                        f"{exc.errors()[:3]}"
                    ) from exc
                messages.append({"role": "user", "content": _CORRECTION.format(raw=raw)})
                continue
        # Inalcanzable: el bucle siempre retorna o lanza.
        raise ExtractionError(
            "No se pudo extraer un análisis válido del sueño."
        )  # pragma: no cover
