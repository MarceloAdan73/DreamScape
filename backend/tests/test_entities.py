"""Tests de la identidad de las entidades (nombre único) y su purga.

Cubre los dos bugs que impedían ver patrones: el mismo nombre creado con dos
tipos (`ex` como símbolo y como persona) y las entidades que quedaban huérfanas
al borrar sueños de a uno.
"""

from __future__ import annotations

import json

import pytest
from app.core import llm as llm_module
from app.models import db as db_module
from app.models.db import DreamEntity, Entity, _migrate_entities_unique_by_name
from app.services.patterns import _consolidate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from tests.fakes import FakeProvider


def _monkeypatch_provider(monkeypatch: pytest.MonkeyPatch, fake: FakeProvider) -> None:
    monkeypatch.setattr(llm_module, "get_provider", lambda settings=None, runtime=None: fake)


def _analysis(*, symbols: list[str], people: list[str], places: list[str] | None = None) -> str:
    return json.dumps(
        {
            "title": "Un sueño de prueba",
            "symbols": [{"name": name, "interpretation": f"Sobre {name}."} for name in symbols],
            "emotions": [],
            "people": people,
            "places": places or [],
            "one_line_insight": "Una línea.",
            "summary": "Un resumen de prueba.",
        }
    )


async def _entities_named(name: str) -> list[tuple[int, str]]:
    async with db_module.async_session_factory() as session:
        rows = await session.execute(
            select(Entity.id, Entity.type).where(Entity.name == name)
        )
        return list(rows.all())


async def _entity_names() -> set[str]:
    async with db_module.async_session_factory() as session:
        rows = await session.execute(select(Entity.name))
        return {row[0] for row in rows.all()}


async def test_same_name_in_two_categories_is_one_entity(client, monkeypatch) -> None:
    """'ex' como símbolo y como persona es la misma entidad, no dos."""
    fake = FakeProvider(chat_responses=[_analysis(symbols=["ex"], people=["ex"])])
    _monkeypatch_provider(monkeypatch, fake)

    await client.post("/api/dreams", json={"text": "Soñé con mi ex."})

    entities = await _entities_named("ex")
    assert len(entities) == 1, f"se duplicó la entidad: {entities}"
    # Gana el tipo más específico: `symbol` es el comodín.
    assert entities[0][1] == "person"

    async with db_module.async_session_factory() as session:
        links = await session.scalar(
            select(func.count())
            .select_from(DreamEntity)
            .where(DreamEntity.entity_id == entities[0][0])
        )
    assert links == 1, "el sueño debe quedar con un solo vínculo a la entidad"


async def test_more_specific_type_promotes_existing_entity(client, monkeypatch) -> None:
    """Si un sueño trae 'gato' como símbolo y otro como persona, se promueve."""
    first = FakeProvider(chat_responses=[_analysis(symbols=["gato"], people=[])])
    _monkeypatch_provider(monkeypatch, first)
    await client.post("/api/dreams", json={"text": "El gato."})

    second = FakeProvider(chat_responses=[_analysis(symbols=[], people=["gato"])])
    _monkeypatch_provider(monkeypatch, second)
    await client.post("/api/dreams", json={"text": "La persona gato."})

    entities = await _entities_named("gato")
    assert len(entities) == 1
    assert entities[0][1] == "person"


async def test_deleting_a_dream_purges_orphan_entities(client, monkeypatch) -> None:
    """Borrar un sueño no debe dejar entidades que ya no usa nadie."""
    first = FakeProvider(chat_responses=[_analysis(symbols=["océano"], people=[])])
    _monkeypatch_provider(monkeypatch, first)
    await client.post("/api/dreams", json={"text": "El océano."})

    second = FakeProvider(chat_responses=[_analysis(symbols=["luna"], people=[])])
    _monkeypatch_provider(monkeypatch, second)
    await client.post("/api/dreams", json={"text": "La luna."})

    assert {"océano", "luna"} <= await _entity_names()

    first_dream = (await client.get("/api/dreams")).json()["items"][-1]
    assert (await client.delete(f"/api/dreams/{first_dream['id']}")).status_code == 204

    names = await _entity_names()
    assert "océano" not in names, "la entidad del sueño borrado quedó huérfana"
    assert "luna" in names, "la entidad del sueño vivo no debe tocarse"


async def test_deleting_a_dream_keeps_shared_entities(client, monkeypatch) -> None:
    """Una entidad que sigue en otro sueño sobrevive al borrado."""
    shared = _analysis(symbols=["océano"], people=[])
    fake = FakeProvider(chat_responses=[shared, shared])
    _monkeypatch_provider(monkeypatch, fake)

    await client.post("/api/dreams", json={"text": "El océano."})
    await client.post("/api/dreams", json={"text": "Otra vez el océano."})

    dream = (await client.get("/api/dreams")).json()["items"][-1]
    await client.delete(f"/api/dreams/{dream['id']}")

    assert "océano" in await _entity_names()


def test_consolidate_keeps_max_count_not_sum() -> None:
    """El mismo nombre con dos tipos no debe sumar sueños ya contados."""
    rows = [("ex", "symbol", 3), ("ex", "person", 2), ("agua", "symbol", 2)]
    consolidated = _consolidate(rows)

    assert set(consolidated) == {"ex", "agua"}
    assert consolidated["ex"]["dream_count"] == 3, "sumar contaría de más"
    assert consolidated["agua"]["dream_count"] == 2


def test_consolidate_is_case_insensitive() -> None:
    consolidated = _consolidate([("Ex", "person", 2), ("ex", "symbol", 2)])
    assert len(consolidated) == 1
    assert consolidated["ex"]["dream_count"] == 2


async def test_migration_fuses_duplicated_entities(tmp_path) -> None:
    """Una base vieja (UNIQUE(name, type)) queda con una fila por nombre.

    Es una migración de datos sobre información del usuario: si falla, se
    pierden o duplican patrones en silencio, así que va testeada.
    """
    db_path = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT NOT NULL,"
            " type TEXT NOT NULL, created_at DATETIME NOT NULL, UNIQUE(name, type))"
        )
        await conn.exec_driver_sql(
            "CREATE TABLE dream_entities (id INTEGER PRIMARY KEY, dream_id INTEGER NOT NULL,"
            " entity_id INTEGER NOT NULL, weight FLOAT NOT NULL, score FLOAT,"
            " interpretation TEXT, UNIQUE(dream_id, entity_id))"
        )
        # 'ex' como símbolo (1) y como persona (2), más una entidad huérfana (3).
        await conn.exec_driver_sql(
            "INSERT INTO entities (id, name, type, created_at) VALUES"
            " (1, 'ex', 'symbol', '2026-01-01'),"
            " (2, 'ex', 'person', '2026-01-01'),"
            " (3, 'fantasma', 'symbol', '2026-01-01')"
        )
        await conn.exec_driver_sql(
            "INSERT INTO dream_entities (id, dream_id, entity_id, weight) VALUES"
            " (1, 1, 1, 1.0), (2, 1, 2, 1.0), (3, 2, 1, 1.0)"
        )

        await _migrate_entities_unique_by_name(conn)

        entities = (await conn.exec_driver_sql("SELECT name, type FROM entities")).all()
        links = (
            await conn.exec_driver_sql("SELECT dream_id, entity_id FROM dream_entities")
        ).all()

    await engine.dispose()

    assert entities == [("ex", "person")], "sobrevive el tipo más específico"
    assert 3 not in {row[1] for row in links}, "la entidad huérfana se elimina"
    assert sorted(links) == [(1, 2), (2, 2)], "los vínculos se reapuntan sin duplicar"


async def test_migration_is_idempotent(tmp_path) -> None:
    """Correrla dos veces sobre una base ya migrada no debe romper nada."""
    db_path = tmp_path / "twice.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE entities (id INTEGER PRIMARY KEY, name TEXT NOT NULL,"
            " type TEXT NOT NULL, created_at DATETIME NOT NULL, UNIQUE(name, type))"
        )
        await conn.exec_driver_sql(
            "CREATE TABLE dream_entities (id INTEGER PRIMARY KEY, dream_id INTEGER NOT NULL,"
            " entity_id INTEGER NOT NULL, weight FLOAT NOT NULL, score FLOAT,"
            " interpretation TEXT, UNIQUE(dream_id, entity_id))"
        )
        await conn.exec_driver_sql(
            "INSERT INTO entities (id, name, type, created_at) VALUES"
            " (1, 'ex', 'symbol', '2026-01-01'), (2, 'ex', 'person', '2026-01-01')"
        )
        await conn.exec_driver_sql(
            "INSERT INTO dream_entities (id, dream_id, entity_id, weight) VALUES"
            " (1, 1, 1, 1.0), (2, 2, 2, 1.0)"
        )

        await _migrate_entities_unique_by_name(conn)
        await _migrate_entities_unique_by_name(conn)

        entities = (await conn.exec_driver_sql("SELECT name, type FROM entities")).all()
        links = (
            await conn.exec_driver_sql("SELECT dream_id, entity_id FROM dream_entities")
        ).all()

    await engine.dispose()

    assert entities == [("ex", "person")]
    assert sorted(links) == [(1, 2), (2, 2)]
