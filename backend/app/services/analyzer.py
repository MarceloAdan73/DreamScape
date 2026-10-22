"""Orquestador del análisis de un sueño (corre en background con FastAPI).

Pipeline de `run_dream_analysis(dream_id)`:
1. Marca el sueño como `processing`.
2. `DreamExtractor` → `DreamAnalysis` validado (reintentos incluidos).
3. Persiste entidades y vínculos sueño↔entidad (transaccional).
4. `SimilarityIndex` → embeddings + top-N similares → aristas `dream_links`.
5. Guarda insight de una línea, resumen y estado `completed`.

Cualquier fallo del LLM se LOGUEA (nunca se silencia) y marca `failed` con la
razón, dejando el sueño listo para reintento manual (`POST /api/analysis/reanalyze`).
El registro del sueño nunca se bloquea por un fallo de IA.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm as llm_module
from app.core.config import get_settings
from app.core.runtime import current_runtime
from app.models import db
from app.models.db import Dream, DreamEntity, DreamLink, Entity, utcnow
from app.schemas.dream import DreamAnalysis
from app.services.dream_extractor import DreamExtractor
from app.services.similarity import SimilarCandidate, SimilarityIndex

logger = logging.getLogger("dreamscape.analyzer")

# Un solo análisis a la vez: dos tareas concurrentes borrarían/insertarían el
# mismo par de `dream_links` y chocarían con el UNIQUE (source, target).
_ANALYSIS_LOCK = asyncio.Lock()

EntityType = Literal["symbol", "emotion", "person", "place"]

# Especificidad del tipo: si un mismo nombre llega con dos tipos ("ex" como
# símbolo y como persona), gana el más informativo. `symbol` es el comodín.
_TYPE_SPECIFICITY: dict[str, int] = {"symbol": 0, "emotion": 1, "place": 2, "person": 3}


def _more_specific(current: str, candidate: str) -> bool:
    return _TYPE_SPECIFICITY.get(candidate, 0) > _TYPE_SPECIFICITY.get(current, 0)


async def _get_or_create_entity(session: AsyncSession, name: str, etype: EntityType) -> Entity:
    """Devuelve la entidad con ese nombre, creándola si no existe.

    La identidad es el nombre, no el par (nombre, tipo): el modelo la garantiza
    con UNIQUE(name). Si el nombre ya existe con un tipo menos específico, se
    promueve al nuevo para no perder información.
    """
    result = await session.scalars(select(Entity).where(Entity.name == name))
    entity: Entity | None = result.first()
    if entity is None:
        entity = Entity(name=name, type=etype)
        session.add(entity)
        await session.flush()
    elif _more_specific(entity.type, etype):
        entity.type = etype
    return entity


def _normalize_entity_name(raw: str) -> str:
    '''Normaliza nombre de entidad: minúscula, sin artículo y sin compuestos.

    Un compuesto ("gato negro", "calma rara") se reduce a su palabra
    principal para que pueda fusionarse con otras menciones del mismo concepto.
    '''
    name = raw.strip().lower()
    for article in ("el ", "la ", "los ", "las ", "un ", "una "):
        if name.startswith(article):
            name = name[len(article):]
            break
    # Colapsa cualquier compuesto a su primera palabra (la cabeza del concepto).
    name = name.split()[0] if name.split() else ""
    return name.strip()


async def _persist_entities(
    session: AsyncSession,
    dream_id: int,
    analysis: DreamAnalysis,
) -> None:
    """Persiste entidades y sus pesos/interpretaciones en una sola transacción."""
    # Re-análisis: limpia los vínculos previos del sueño para no chocar con el
    # constraint único (dream_id, entity_id).
    previous = await session.scalars(
        select(DreamEntity).where(DreamEntity.dream_id == dream_id)
    )
    for stale in previous:
        await session.delete(stale)
    await session.flush()

    # `seen` va por nombre, no por (nombre, tipo): la entidad es una sola, así
    # que un nombre repetido en dos categorías debe quedar una vez sola. Se
    # recorren de más específica a menos para que gane el mejor tipo.
    seen: set[str] = set()

    async def link(
        name_raw: str,
        etype: EntityType,
        *,
        weight: float = 1.0,
        score: float | None = None,
        interpretation: str | None = None,
    ) -> None:
        name = _normalize_entity_name(name_raw)
        if not name or name in seen:
            return
        seen.add(name)
        entity = await _get_or_create_entity(session, name, etype)
        session.add(
            DreamEntity(
                dream_id=dream_id,
                entity_id=entity.id,
                weight=weight,
                score=score,
                interpretation=interpretation,
            )
        )

    for person in analysis.people:
        await link(person, "person")

    for place in analysis.places:
        await link(place, "place")

    for emotion in analysis.emotions:
        await link(
            emotion.name,
            "emotion",
            weight=round(emotion.score / 10, 3),
            score=emotion.score,
        )

    for symbol in analysis.symbols:
        await link(symbol.name, "symbol", interpretation=symbol.interpretation)


async def _persist_links(
    session: AsyncSession,
    dream_id: int,
    candidates: list[SimilarCandidate],
) -> None:
    """Reemplaza las aristas del sueño (relación simétrica, orden canónico a<b)."""
    existing = await session.scalars(
        select(DreamLink).where(
            or_(
                DreamLink.source_dream_id == dream_id,
                DreamLink.target_dream_id == dream_id,
            )
        )
    )
    for link in existing:
        await session.delete(link)
    await session.flush()

    seen_pairs: set[tuple[int, int]] = set()
    for candidate in candidates:
        source, target = sorted((dream_id, candidate.dream_id))
        if (source, target) in seen_pairs:
            continue
        # Borra cualquier par existente (por si otro sueño ya lo creó).
        other = await session.scalars(
            select(DreamLink).where(
                DreamLink.source_dream_id == source,
                DreamLink.target_dream_id == target,
            )
        )
        if other.first() is not None:
            seen_pairs.add((source, target))
            continue
        session.add(
            DreamLink(
                source_dream_id=source,
                target_dream_id=target,
                similarity=candidate.similarity,
            )
        )
        seen_pairs.add((source, target))


async def _do_analysis(session: AsyncSession, dream: Dream) -> None:
    settings = get_settings()
    # El proveedor se resuelve según las Settings de la UI (runtime > entorno).
    provider = llm_module.get_provider(settings, current_runtime())

    existing_names_result = await session.scalars(select(Entity.name))
    existing_names = list(existing_names_result.all())

    extractor = DreamExtractor(provider, settings)
    analysis = await extractor.extract(dream.text, vocabulary=existing_names)

    await _persist_entities(session, dream.id, analysis)

    index = SimilarityIndex(settings)
    candidates = await index.index_and_search(
        provider,
        dream.text,
        dream.id,
        settings.similar_top_k,
        settings.similarity_threshold,
    )
    await _persist_links(session, dream.id, candidates)

    dream.title = analysis.title
    dream.one_line_insight = analysis.one_line_insight
    dream.summary = analysis.summary
    dream.analysis_status = "completed"
    dream.analysis_error = None
    dream.analyzed_at = utcnow()
    await session.commit()
    logger.info(
        "Sueño %s analizado: %d símbolos, %d emociones, %d sueños similares",
        dream.id,
        len(analysis.symbols),
        len(analysis.emotions),
        len(candidates),
    )


async def run_dream_analysis(dream_id: int) -> None:
    """Tarea de background: analiza el sueño y actualiza su estado (serializada)."""
    async with _ANALYSIS_LOCK:
        await _run_dream_analysis(dream_id)


async def _run_dream_analysis(dream_id: int) -> None:
    try:
        async with db.async_session_factory() as session:
            dream = await session.get(Dream, dream_id)
            if dream is None:
                logger.warning("No se encontró el sueño %s para analizar.", dream_id)
                return
            dream.analysis_status = "processing"
            await session.commit()
            try:
                await _do_analysis(session, dream)
            except Exception as exc:
                await session.rollback()
                dream.analysis_status = "failed"
                dream.analysis_error = f"{type(exc).__name__}: {exc}"
                dream.analyzed_at = None
                await session.commit()
                logger.exception("El análisis del sueño %s falló.", dream_id)
    except Exception:
        logger.exception("No se pudo abrir una sesión para analizar el sueño %s.", dream_id)
