"""Tests del título instantáneo (provisorio, local, sin IA)."""

from __future__ import annotations

from app.services.instant_title import keywords, make_instant_title
from httpx import AsyncClient


def test_keywords_ignora_stopwords_y_cuenta_frecuencia() -> None:
    text = (
        "Estaba junto a una mujer que era mi pareja, veíamos dormir "
        "un gato con sus crías. El gato ronroneaba junto a la pareja."
    )
    assert keywords(text) == ["pareja", "gato", "mujer"]


def test_keywords_sin_tildes_y_mayusculas() -> None:
    assert keywords("Tormenta, TORMENTA y tormenta en el barco") == ["tormenta", "barco"]


def test_make_instant_title_formato() -> None:
    assert make_instant_title("Gato gato gato perro") == "Gato y perro"
    assert (
        make_instant_title("El barco y la tormenta y la angustia")
        == "Barco, tormenta y angustia"
    )
    assert make_instant_title("Crystal city lights neon") == "Crystal, city y lights"
    assert make_instant_title("Dragon dragon dragon") == "Dragon"


def test_make_instant_title_sin_contenido_devuelve_none() -> None:
    assert make_instant_title("yo y yo") is None
    assert make_instant_title("...") is None


async def test_create_dream_incluye_titulo_instantaneo(client: AsyncClient) -> None:
    response = await client.post(
        "/api/dreams",
        json={"text": "Soñé con un gato que cuidaba a sus crías junto a mi pareja."},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["analysis_status"] == "pending"
    assert body["title"] == "Gato, crías y pareja"
