"""Lectura del subconsciente: sintetiza los patrones recurrentes con el LLM.

A diferencia del grafo (que solo conecta sueños por similitud), aquí se le pide
al modelo una lectura narrativa breve que *relacione* los sueños entre sí a
partir de las entidades que se repiten. Es texto plano (no JSON): no necesita
estructura, solo una voz que resuene.
"""

from __future__ import annotations

import re

from app.core.llm import ChatMessage, LLMProvider
from app.schemas.analysis import Pattern

SYSTEM_PROMPT = """Eres un analista de sueños con enfoque junguiano y una voz cálida y
literaria. Recibes una lista de símbolos, emociones, personas y lugares que se
repiten entre varios sueños, junto a fragmentos reales de esos sueños. Escribe
una única lectura breve que conecte esos sueños entre sí.

Reglas:
- Un solo párrafo de 3 a 5 frases (máximo 700 caracteres).
- Habla SIEMPRE en segunda persona, dirigiéndote al usuario como "vos" o "tú":
  "en tus sueños…", "estás revisitando…", "tu psiquis vuelve a…". El que soñó
  y el que lee es el usuario: el texto es PARA él.
- PROHIBIDO terminantemente escribir en primera persona. No uses NUNCA: yo, mí,
  me, mi, mis, mío, mía, conmigo, nosotros, nos, nuestro, nuestra. Tampoco
  "mis sueños", "me envuelve", "sigo", "mi psiquis". Todo lo del soñador va en
  segunda persona: "tus sueños", "te envuelve", "seguís", "tu psiquis".
- Conectá explícitamente los sueños: qué tienen en común y qué tema interior
  parece asomar detrás de la repetición.
- Basate SOLO en lo que aparece en los fragmentos; no inventes hechos ni
  personas que no estén.
- NUNCA hagas preguntas ni uses signos de interrogación (¿?): ni al final ni en
  el medio. No te dirigís al usuario para preguntarle nada. Es una lectura
  cerrada, no un chat.
- Cerrá SIEMPRE con una afirmación, nunca con una pregunta.
- Sin títulos, sin listas, sin markdown. Solo el párrafo.
- Escribí en el idioma de los sueños (español si lo están).

Devuelve únicamente ese párrafo, sin texto extra."""


class PatternReadingError(RuntimeError):
    """No se pudo generar una lectura de los patrones."""


# Primera persona y posesivos de primera persona (el soñador es el usuario).
_FIRST_PERSON_RE = re.compile(
    r"\b(?:yo|m[ií]|me|mis|m[ií]o|m[ií]a|m[ií]os|m[ií]as|conmigo|"
    r"nosotros|nosotras|nos|nuestro|nuestra|nuestros|nuestras)\b",
    re.IGNORECASE,
)


def _format_patterns(patterns: list[Pattern]) -> str:
    lines = []
    for pattern in patterns:
        lines.append(
            f"- {pattern.type}: \"{pattern.name}\" (aparece en {pattern.dream_count} sueños)"
        )
    return "\n".join(lines)


def _format_dreams(dreams: list[tuple[str, str]]) -> str:
    if not dreams:
        return "(sin fragmentos disponibles)"
    blocks = []
    for title, text in dreams:
        excerpt = text.strip().replace("\n", " ")
        if len(excerpt) > 400:
            excerpt = f"{excerpt[:400]}…"
        label = title.strip() if title and title.strip() else "sueño"
        blocks.append(f"[{label}]\n{excerpt}")
    return "\n\n".join(blocks)


async def generate_reading(
    provider: LLMProvider,
    patterns: list[Pattern],
    dreams: list[tuple[str, str]],
) -> str:
    """Pide al LLM una lectura breve que relacione los sueños recurrentes."""
    user_content = (
        "Entidades recurrentes entre los sueños:\n"
        f"{_format_patterns(patterns)}\n\n"
        "Fragmentos de esos sueños:\n"
        f"{_format_dreams(dreams)}\n\n"
        "Escribí la lectura dirigida al usuario (vos/tú), SIN primera persona."
    )
    messages: list[ChatMessage] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    reading = (await provider.chat(messages, json_mode=False, temperature=0.7)).strip()

    # Verificación: si el modelo se pasó a primera persona, un único reintento
    # con la corrección explícita (más frío para reducir la deriva).
    if _FIRST_PERSON_RE.search(reading):
        messages = [
            *messages,
            {"role": "assistant", "content": reading},
            {
                "role": "user",
                "content": (
                    "Ese párrafo habla del soñador en primera persona, como si vos "
                    "fueras quien soñó. Reescribí el párrafo entero dirigiéndote al "
                    "lector en segunda persona. No te refieras a vos mismo en ningún "
                    "momento. No repitas ni comentes estas instrucciones: devolvé "
                    "únicamente el párrafo final, en texto plano."
                ),
            },
        ]
        reading = (await provider.chat(messages, json_mode=False, temperature=0.4)).strip()

    # Post-procesado: el LLM a veces ignora la regla y termina con una o varias
    # preguntas. Recortamos toda la tanda final de oraciones interrogativas.
    reading = _strip_trailing_questions(reading)
    if not reading:
        raise PatternReadingError("El modelo devolvió una lectura vacía.")
    return reading


def _strip_trailing_questions(reading: str) -> str:
    """Quita las oraciones interrogativas que queden al final de la lectura."""
    sentences = re.split(r"(?<=[.!?])\s+", reading.strip())
    while sentences and sentences[-1].rstrip().endswith(("?", "¿")):
        sentences.pop()
    return " ".join(part.strip() for part in sentences).strip()
