"""Endpoints de la capa IA: re-análisis manual, estado del proveedor.

Fase 3: `/graph` (grafo de sueños para la vista 3D) y `/patterns` (entidades
recurrentes). La carta mensual (`/monthly-letter`) se suma en la fase 4.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm as llm_module
from app.core.config import get_settings
from app.core.runtime import current_runtime
from app.models.db import Dream, get_session
from app.schemas.analysis import GraphPayload, PatternsResponse, ReadingResponse
from app.services.analyzer import run_dream_analysis
from app.services.graph import GraphService
from app.services.pattern_reader import generate_reading
from app.services.patterns import PatternService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/provider-status")
async def provider_status() -> dict[str, str]:
    """Estado del proveedor de IA activo (para mostrar degradación clara en la UI)."""
    status_obj = await llm_module.provider_status(get_settings(), current_runtime())
    return {
        "provider": status_obj.provider,
        "ok": str(status_obj.ok).lower(),
        "detail": status_obj.detail,
    }


@router.post("/reanalyze/{dream_id}", status_code=status.HTTP_202_ACCEPTED)
async def reanalyze_dream(
    dream_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Reintento manual del análisis de un sueño (fallido o para regenerarlo)."""
    dream = await session.get(Dream, dream_id)
    if dream is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sueño no encontrado.")
    if dream.analysis_status in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El sueño ya está en análisis ('{dream.analysis_status}').",
        )

    dream.analysis_status = "pending"
    dream.analysis_error = None
    await session.commit()

    background_tasks.add_task(run_dream_analysis, dream.id)
    return {"status": "queued", "dream_id": str(dream_id)}


@router.get("/graph", response_model=GraphPayload)
async def dream_graph(
    limit: int = Query(default=200, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> GraphPayload:
    """Grafo de conexiones entre sueños (nodos + aristas) para la vista 3D."""
    return await GraphService(session).build(limit)


@router.get("/patterns", response_model=PatternsResponse)
async def dream_patterns(
    min_count: int = Query(default=2, ge=1, le=50),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> PatternsResponse:
    """Entidades recurrentes entre los sueños analizados, por frecuencia."""
    return await PatternService(session).build(min_count=min_count, limit=limit)


@router.post("/patterns/reading", response_model=ReadingResponse)
async def patterns_reading(
    min_count: int = Query(default=2, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> ReadingResponse:
    """Lectura breve generada por IA que relaciona los sueños recurrentes."""
    service = PatternService(session)
    patterns_response = await service.build(min_count=min_count, limit=20)
    if not patterns_response.patterns:
        return ReadingResponse(
            detail=(
                "Todavía no hay entidades repetidas entre tus sueños. "
                "Registrá más sueños con símbolos en común para generar una lectura."
            )
        )

    dreams = await service.exemplar_texts(
        [pattern.exemplar_dream_id for pattern in patterns_response.patterns]
    )
    try:
        provider = llm_module.get_provider(get_settings(), current_runtime())
        reading = await generate_reading(provider, patterns_response.patterns, dreams)
    except Exception as exc:  # noqa: BLE001 - se traduce a un detalle claro para la UI
        return ReadingResponse(detail=f"No se pudo generar la lectura: {exc}")

    return ReadingResponse(reading=reading)
