"""Servicio de patrones: detecta entidades recurrentes entre sueños.

Un "patrón" es una entidad (símbolo, emoción, persona o lugar) que aparece
en 2 o más sueños distintos. Se ordena por frecuencia de sueños (no por
presencia total, para no favorecer sueños con análisis muy recargados).

Futuro (Fase 3 avanzada): clústeres de sueños por similitud y estacionalidad
temporal. Hoy se entrega el ranking de recurrencia que alimenta la vista de
patrones del frontend.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypedDict, cast

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Dream, DreamEntity, Entity
from app.schemas.analysis import Pattern, PatternsResponse
from app.schemas.dream import EntityType


class _Consolidated(TypedDict):
    name: str
    types: list[str]
    dream_count: int


# Mismo criterio que el upsert de entidades: gana el tipo más informativo y
# `symbol` es el comodín.
_TYPE_SPECIFICITY: dict[str, int] = {"symbol": 0, "emotion": 1, "place": 2, "person": 3}


def _type_specificity(etype: str) -> int:
    return _TYPE_SPECIFICITY.get(etype, 0)


def _consolidate(rows: Sequence[tuple[str, str, int] | Any]) -> dict[str, _Consolidated]:
    """Funde filas del mismo nombre en un patrón cada una.

    `entities` es única por nombre, así que hoy cada fila ya es un patrón. La
    consolidación queda como red de seguridad para bases viejas que aún tengan
    el mismo nombre con dos tipos: el conteo se queda con el MAYOR de los dos,
    nunca con la suma, que contaría de más los sueños ya contados.
    """
    consolidated: dict[str, _Consolidated] = {}
    for name, etype, count in rows:
        key = name.lower()
        entry = consolidated.setdefault(key, {"name": name, "types": [], "dream_count": 0})
        entry["types"].append(etype)
        entry["dream_count"] = max(entry["dream_count"], int(count))
    return consolidated


class PatternService:
    """Detecta y rankea entidades recurrentes sobre los sueños analizados."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build(self, min_count: int, limit: int) -> PatternsResponse:
        analyzed = await self._session.scalar(
            select(func.count()).select_from(Dream).where(Dream.analysis_status == "completed")
        )
        dreams_analyzed = int(analyzed if analyzed is not None else 0)

        rows = (
            await self._session.execute(
                select(
                    Entity.name,
                    Entity.type,
                    func.count(distinct(DreamEntity.dream_id)).label("dream_count"),
                )
                .join(DreamEntity, DreamEntity.entity_id == Entity.id)
                .group_by(Entity.name)
                .having(func.count(distinct(DreamEntity.dream_id)) >= min_count)
                .order_by(func.count(distinct(DreamEntity.dream_id)).desc())
                .limit(limit)
            )
        ).all()

        if not rows:
            return PatternsResponse(dreams_analyzed=dreams_analyzed, total=0, patterns=[])

        consolidated = _consolidate(rows)
        names = list(consolidated.keys())

        last_seen = await self._recent_dream_dates_by_name(names)
        exemplars = await self._exemplar_dream_ids_by_name(names)
        interpretations = await self._sample_interpretations_by_name(names)

        patterns = []
        for key, entry in consolidated.items():
            primary_type = max(entry["types"], key=_type_specificity)
            patterns.append(
                Pattern(
                    name=entry["name"],
                    type=cast(EntityType, primary_type),
                    dream_count=entry["dream_count"],
                    last_seen_at=last_seen.get(key),
                    exemplar_dream_id=exemplars.get(key),
                    interpretation=interpretations.get(key),
                )
            )
        return PatternsResponse(
            dreams_analyzed=dreams_analyzed,
            total=len(patterns),
            patterns=patterns,
        )

    async def exemplar_texts(
        self, dream_ids: Sequence[int | None]
    ) -> list[tuple[str, str]]:
        """Devuelve (título, texto) de los sueños de ejemplo, sin duplicados."""
        unique = [dream_id for dream_id in dict.fromkeys(dream_ids) if dream_id is not None]
        if not unique:
            return []
        rows = (
            await self._session.execute(
                select(Dream.title, Dream.text)
                .where(Dream.id.in_(unique))
                .order_by(Dream.created_at.desc())
            )
        ).all()
        return [(title or "", text) for title, text in rows]

    async def _recent_dream_dates_by_name(
        self, names: Sequence[str]
    ) -> dict[str, datetime]:
        """Fecha del último sueño por nombre de entidad."""
        if not names:
            return {}
        rows = (
            await self._session.execute(
                select(
                    Entity.name,
                    func.max(
                        func.coalesce(Dream.analyzed_at, Dream.created_at)
                    ).label("last_at"),
                )
                .join(DreamEntity, DreamEntity.entity_id == Entity.id)
                .join(Dream, Dream.id == DreamEntity.dream_id)
                .where(Entity.name.in_(names))
                .group_by(Entity.name)
            )
        ).all()
        return {row[0].lower(): row[1] for row in rows}

    async def _exemplar_dream_ids_by_name(self, names: Sequence[str]) -> dict[str, int]:
        """Un sueño de ejemplo por nombre de entidad (el más reciente)."""
        if not names:
            return {}
        rows = (
            await self._session.execute(
                select(
                    Entity.name,
                    DreamEntity.dream_id,
                    func.max(Dream.created_at).label("max_created"),
                )
                .join(DreamEntity, DreamEntity.entity_id == Entity.id)
                .join(Dream, Dream.id == DreamEntity.dream_id)
                .where(Entity.name.in_(names))
                .group_by(Entity.name, DreamEntity.dream_id)
                .order_by(func.max(Dream.created_at).desc())
            )
        ).all()
        exemplar: dict[str, int] = {}
        for name, dream_id, _ in rows:
            exemplar.setdefault(name.lower(), dream_id)
        return exemplar

    async def _sample_interpretations_by_name(
        self, names: Sequence[str]
    ) -> dict[str, str]:
        """Interpretación de muestra por nombre de entidad."""
        if not names:
            return {}
        rows = (
            await self._session.execute(
                select(Entity.name, DreamEntity.interpretation)
                .join(DreamEntity, DreamEntity.entity_id == Entity.id)
                .where(
                    Entity.name.in_(names),
                    DreamEntity.interpretation.is_not(None),
                )
            )
        ).all()
        found: dict[str, str] = {}
        for name, interpretation in rows:
            if interpretation is not None and name.lower() not in found:
                found[name.lower()] = interpretation
        return found