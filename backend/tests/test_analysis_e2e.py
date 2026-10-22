"""Tests e2e: POST /api/dreams → análisis en background (LLM mock).

Con httpx ASGITransport la tarea de background corre dentro del mismo `await`
del POST (Starlette agota las BackgroundTasks tras enviar la respuesta), así
que el e2e verifica el pipeline completo sin hilos ni sleeps.
"""

from __future__ import annotations

import pytest
from app.core import llm as llm_module
from app.core.llm import ProviderUnavailable
from app.models import db as db_module
from app.models.db import DreamEntity, DreamLink
from sqlalchemy import select

from tests.fakes import FakeProvider


def _monkeypatch_provider(monkeypatch: pytest.MonkeyPatch, fake: FakeProvider) -> None:
    monkeypatch.setattr(llm_module, "get_provider", lambda settings=None, runtime=None: fake)


async def test_e2e_post_analyzas_in_background(client, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    created = await client.post("/api/dreams", json={"text": "Soñé con un océano de tinta."})
    assert created.status_code == 201
    dream_id = created.json()["id"]

    detail = (await client.get(f"/api/dreams/{dream_id}")).json()
    assert detail["analysis_status"] == "completed"
    assert detail["one_line_insight"] == "La tinta es la memoria sin nombrar."

    # Entidades y relaciones persistidas en la base del test.
    async with db_module.async_session_factory() as session:
        dream_entities = (await session.scalars(select(DreamEntity))).all()
    names = {(row.entity.name, row.entity.type) for row in dream_entities}
    assert ("océano", "symbol") in names
    assert ("asombro", "emotion") in names
    assert ("mamá", "person") in names


async def test_two_similar_dreams_create_link(client, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    await client.post("/api/dreams", json={"text": "Primer sueño de prueba."})
    await client.post("/api/dreams", json={"text": "Segundo sueño de prueba."})

    async with db_module.async_session_factory() as session:
        links = (await session.scalars(select(DreamLink))).all()
    # Embeddings idénticos del fake → ambos sueños se conectan (una sola arista A-B).
    assert len(links) == 1
    assert links[0].similarity == pytest.approx(1.0, abs=0.0001)


async def test_provider_failure_marks_failed_and_reanalyze_recovers(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeProvider(chat_error=ProviderUnavailable("No se pudo conectar con Ollama"))
    _monkeypatch_provider(monkeypatch, fake)

    created = await client.post("/api/dreams", json={"text": "Sueño sin análisis posible."})
    dream_id = created.json()["id"]

    failed = (await client.get(f"/api/dreams/{dream_id}")).json()
    assert failed["analysis_status"] == "failed"
    assert "Ollama" in failed["analysis_error"]

    # Ollama "se levanta" y el reintento manual recupera el sueño.
    fake.chat_error = None
    requeued = await client.post(f"/api/analysis/reanalyze/{dream_id}")
    assert requeued.status_code == 202

    recovered = (await client.get(f"/api/dreams/{dream_id}")).json()
    assert recovered["analysis_status"] == "completed"
    assert recovered["one_line_insight"] == "La tinta es la memoria sin nombrar."


async def test_reanalyze_allows_completed_dream(client, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    created = await client.post("/api/dreams", json={"text": "Un sueño sano."})
    dream_id = created.json()["id"]

    status = (await client.get(f"/api/dreams/{dream_id}")).json()
    assert status["analysis_status"] == "completed"
    assert status["title"] == "El océano que guardaba la memoria"

    # Un sueño ya completado puede reanalizarse (p. ej. tras cambiar de modelo).
    response = await client.post(f"/api/analysis/reanalyze/{dream_id}")
    assert response.status_code == 202
    requeued = (await client.get(f"/api/dreams/{dream_id}")).json()
    assert requeued["analysis_status"] == "completed"


async def test_provider_status_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    response = await client.get("/api/analysis/provider-status")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fake"
    assert body["ok"] == "true"
