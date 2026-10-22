"""Tests del DreamExtractor: validación de JSON, reintentos y agotamiento."""

from __future__ import annotations

import pytest
from app.core.config import get_settings
from app.schemas.dream import DreamAnalysis
from app.services.dream_extractor import DreamExtractor, ExtractionError, _extract_json_block

from tests.fakes import DEFAULT_ANALYSIS_JSON, INVALID_SCHEMA_JSON, FakeProvider


async def test_extract_valid_response() -> None:
    provider = FakeProvider(chat_responses=[DEFAULT_ANALYSIS_JSON])
    extractor = DreamExtractor(provider, get_settings())

    analysis = await extractor.extract("Soñé con un océano de tinta.")

    assert isinstance(analysis, DreamAnalysis)
    assert analysis.symbols[0].name == "océano"
    assert analysis.emotions[0].score == 8.0
    assert analysis.one_line_insight == "La tinta es la memoria sin nombrar."


async def test_extract_recovers_from_non_json_response() -> None:
    provider = FakeProvider(chat_responses=["esto no es json", DEFAULT_ANALYSIS_JSON])
    extractor = DreamExtractor(provider, get_settings())

    analysis = await extractor.extract("Un sueño cualquiera.")

    assert analysis.one_line_insight
    assert len(provider.chat_calls) == 2
    # El segundo mensaje de la llamada corregida contiene la respuesta anterior.
    assert "esto no es json" in provider.chat_calls[1][-1]["content"]


async def test_extract_recovers_from_invalid_schema() -> None:
    provider = FakeProvider(chat_responses=[INVALID_SCHEMA_JSON, DEFAULT_ANALYSIS_JSON])
    extractor = DreamExtractor(provider, get_settings())

    analysis = await extractor.extract("Otro sueño.")

    assert analysis.one_line_insight
    assert len(provider.chat_calls) == 2


async def test_extract_json_block_strips_markdown_fences() -> None:
    block = "```json\n" + DEFAULT_ANALYSIS_JSON + "\n```"
    extracted = _extract_json_block(block)
    assert extracted is not None
    assert extracted.startswith("{")


async def test_extract_fails_after_max_attempts() -> None:
    settings = get_settings()
    attempts = 1 + settings.llm_max_retries
    provider = FakeProvider(chat_responses=["no es json"] * attempts)
    extractor = DreamExtractor(provider, settings)

    with pytest.raises(ExtractionError):
        await extractor.extract("Sueño que nunca logra analizarse.")

    assert len(provider.chat_calls) == attempts
