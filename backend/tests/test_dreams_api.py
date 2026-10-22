"""Tests del núcleo: salud, CRUD y validación de sueños."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_list_dreams_empty(client: AsyncClient) -> None:
    response = await client.get("/api/dreams")
    assert response.status_code == 200
    body = response.json()
    assert body == {"total": 0, "items": []}


async def test_create_dream_returns_201_and_pending(client: AsyncClient) -> None:
    response = await client.post(
        "/api/dreams",
        json={"text": "Soñé que volaba sobre una ciudad de cristal.", "mood_on_wake": "asombro"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["analysis_status"] == "pending"
    assert body["mood_on_wake"] == "asombro"
    assert body["one_line_insight"] is None


async def test_get_dream_by_id(client: AsyncClient) -> None:
    created = await client.post("/api/dreams", json={"text": "Un río de tinta negra."})
    dream_id = created.json()["id"]

    response = await client.get(f"/api/dreams/{dream_id}")
    assert response.status_code == 200
    assert response.json()["text"] == "Un río de tinta negra."


async def test_get_missing_dream_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/dreams/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Sueño no encontrado."


async def test_delete_dream(client: AsyncClient) -> None:
    created = await client.post("/api/dreams", json={"text": "Una puerta sin pomo."})
    dream_id = created.json()["id"]

    deleted = await client.delete(f"/api/dreams/{dream_id}")
    assert deleted.status_code == 204

    after = await client.get("/api/dreams")
    assert after.json()["total"] == 0


async def test_create_rejects_empty_text(client: AsyncClient) -> None:
    response = await client.post("/api/dreams", json={"text": "   "})
    assert response.status_code == 422


async def test_list_is_ordered_newest_first(client: AsyncClient) -> None:
    for text in ("primer sueño", "segundo sueño", "tercer sueño"):
        await client.post("/api/dreams", json={"text": text})

    response = await client.get("/api/dreams")
    texts = [item["text"] for item in response.json()["items"]]
    assert texts == ["tercer sueño", "segundo sueño", "primer sueño"]
