"""Endpoints CRUD de sueños.

En esta fase (núcleo) el registro persiste el sueño y responde de inmediato.
El disparo del análisis por IA se conecta en la capa IA (Fase 2) como
`BackgroundTask`, sin bloquear nunca la respuesta del registro.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.db import Dream, DreamEntity, DreamLink, Entity, get_session
from app.schemas.dream import DreamCreate, DreamList, DreamRead
from app.services.analyzer import run_dream_analysis
from app.services.instant_title import make_instant_title
from app.services.similarity import SimilarityIndex

router = APIRouter(prefix="/dreams", tags=["dreams"])

logger = logging.getLogger("dreamscape.dreams")


async def _purge_orphan_entities(session: AsyncSession) -> None:
    """Borra las entidades que quedaron sin ningún vínculo.

    El cascade del ORM se lleva los `dream_entities` del sueño, pero no las
    filas de `entities`: sin esta pasada la tabla crece sin límite y arrastra
    nombres viejos que ya no le importan a nadie.
    """
    await session.execute(
        delete(Entity).where(
            ~Entity.id.in_(select(DreamEntity.entity_id).distinct())
        )
    )


@router.post("", response_model=DreamRead, status_code=status.HTTP_201_CREATED)
async def create_dream(
    payload: DreamCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> Dream:
    """Registra un sueño y dispara el análisis por IA en background.

    La respuesta 201 NO espera a la IA (regla de oro: registrar nunca se bloquea).
    El análisis corre después de enviada la respuesta y actualiza el sueño.
    """
    dream = Dream(
        text=payload.text,
        # Título provisorio instantáneo (local); la IA lo reemplaza al analizar.
        title=make_instant_title(payload.text),
        mood_on_wake=payload.mood_on_wake,
        dreamed_at=payload.dreamed_at,
        analysis_status="pending",
    )
    session.add(dream)
    await session.commit()
    await session.refresh(dream)

    background_tasks.add_task(run_dream_analysis, dream.id)
    return dream


@router.get("", response_model=DreamList)
async def list_dreams(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> DreamList:
    """Lista los sueños, más recientes primero."""
    total = await session.scalar(select(func.count()).select_from(Dream))
    result = await session.scalars(
        select(Dream).order_by(Dream.created_at.desc()).limit(limit).offset(offset)
    )
    items = [DreamRead.model_validate(dream) for dream in result.all()]
    return DreamList(total=total or 0, items=items)


@router.get("/{dream_id}", response_model=DreamRead)
async def get_dream(
    dream_id: int,
    session: AsyncSession = Depends(get_session),
) -> Dream:
    """Devuelve un sueño por id (incluye `one_line_insight` si ya se analizó)."""
    dream = await session.get(Dream, dream_id)
    if dream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sueño no encontrado.")
    return dream


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_dreams(session: AsyncSession = Depends(get_session)) -> None:
    """Reinicia el diario: borra TODOS los sueños, sus vínculos y entidades.

    Operación irreversible (zona de riesgo de la UI). También vacía el índice
    de similitud de ChromaDB para no dejar vectores huérfanos.
    """
    # SQLite no aplica ON DELETE CASCADE salvo PRAGMA foreign_keys=ON: borramos
    # hijos explícitamente para no dejar filas huérfanas.
    await session.execute(delete(DreamEntity))
    await session.execute(delete(DreamLink))
    await session.execute(delete(Dream))
    await session.execute(delete(Entity))
    await session.commit()

    try:
        await SimilarityIndex(get_settings()).clear()
    except Exception:  # noqa: BLE001 - el borrado de datos ya se confirmó
        logger.exception("No se pudo vaciar el índice de similitud tras el reinicio.")


@router.delete("/{dream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dream(
    dream_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Elimina un sueño y sus relaciones (cascade)."""
    dream = await session.get(Dream, dream_id)
    if dream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sueño no encontrado.")
    await session.delete(dream)
    await session.flush()
    await _purge_orphan_entities(session)
    await session.commit()
