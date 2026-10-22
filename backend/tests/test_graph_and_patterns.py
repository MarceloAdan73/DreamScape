"""Tests de Fase 3: endpoints de grafo y de patrones (sobre el pipeline e2e)."""

from __future__ import annotations

import pytest
from app.core import llm as llm_module

from tests.fakes import FakeProvider


def _monkeypatch_provider(monkeypatch: pytest.MonkeyPatch, fake: FakeProvider) -> None:
    monkeypatch.setattr(llm_module, "get_provider", lambda settings=None, runtime=None: fake)


async def test_graph_empty(client) -> None:
    response = await client.get("/api/analysis/graph")
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}


async def test_graph_returns_nodes_and_links(client, monkeypatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    await client.post("/api/dreams", json={"text": "Primer sueño de prueba."})
    await client.post("/api/dreams", json={"text": "Segundo sueño de prueba."})

    response = await client.get("/api/analysis/graph")
    assert response.status_code == 200
    body = response.json()
    assert len(body["nodes"]) == 2
    # Los embeddings idénticos del fake conectan ambos sueños (una sola arista).
    assert len(body["edges"]) == 1
    edge = body["edges"][0]
    assert edge["similarity"] == pytest.approx(1.0, abs=0.0001)
    node_ids = {node["id"] for node in body["nodes"]}
    assert {edge["source"], edge["target"]} == node_ids


async def test_graph_limit(client, monkeypatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    for n in range(5):
        await client.post("/api/dreams", json={"text": f"Sueño {n}."})

    response = await client.get("/api/analysis/graph", params={"limit": 2})
    assert len(response.json()["nodes"]) == 2


async def test_patterns_detect_recurrent_entities(client, monkeypatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    # El fake siempre devuelve océano/asombro/mamá → aparecen en ambos sueños.
    await client.post("/api/dreams", json={"text": "Soñé con un océano."})
    await client.post("/api/dreams", json={"text": "Soñé de nuevo con agua."})

    response = await client.get("/api/analysis/patterns")
    assert response.status_code == 200
    body = response.json()
    assert body["dreams_analyzed"] == 2
    by_name = {pattern["name"]: pattern for pattern in body["patterns"]}
    assert by_name["océano"]["dream_count"] == 2
    assert by_name["asombro"]["dream_count"] == 2
    assert by_name["mamá"]["type"] == "person"
    assert by_name["océano"]["type"] == "symbol"


async def test_patterns_empty(client) -> None:
    response = await client.get("/api/analysis/patterns")
    assert response.status_code == 200
    assert response.json() == {"dreams_analyzed": 0, "total": 0, "patterns": []}


async def test_patterns_min_count_filters(client, monkeypatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    # Un solo sueño → ninguna entidad aparece en >= 2 sueños.
    await client.post("/api/dreams", json={"text": "Un sueño único."})

    response = await client.get("/api/analysis/patterns")
    body = response.json()
    assert body["dreams_analyzed"] == 1
    assert body["total"] == 0

    high = await client.get("/api/analysis/patterns", params={"min_count": 1})
    assert high.json()["total"] > 0


async def test_patterns_interpretation_sample(client, monkeypatch) -> None:
    fake = FakeProvider()
    _monkeypatch_provider(monkeypatch, fake)

    await client.post("/api/dreams", json={"text": "Agua en la noche."})
    await client.post("/api/dreams", json={"text": "Otra noche con agua."})

    patterns = (
        await client.get("/api/analysis/patterns", params={"min_count": 1})
    ).json()["patterns"]
    symbol = next(item for item in patterns if item["type"] == "symbol")
    assert symbol["interpretation"] == "El océano es el inconsciente extendido."

    # El sueño de ejemplo existe y es uno de los creados.
    exemplar = symbol["exemplar_dream_id"]
    detail = (await client.get(f"/api/dreams/{exemplar}")).json()
    assert detail["analysis_status"] == "completed"