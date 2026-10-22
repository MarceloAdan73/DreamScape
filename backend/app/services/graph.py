"""Servicio de grafo: arma el payload de nodos y aristas para la vista 3D.

Nodos = sueños (más recientes primero), aristas = `DreamLink` simétricos.
Se limita la consulta con un `limit` porque el grafo 3D no necesita todos los
sueños históricos para renderizar.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Dream, DreamLink
from app.schemas.analysis import GraphEdge, GraphNode, GraphPayload


class GraphService:
    """Construye el payload del grafo de sueños y sus conexiones."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build(self, limit: int) -> GraphPayload:
        dreams = (
            await self._session.scalars(
                select(Dream).order_by(Dream.created_at.desc()).limit(limit)
            )
        ).all()

        nodes: list[GraphNode] = [
            GraphNode(
                id=dream.id,
                title=dream.title,
                preview=dream.text[:120],
                analysis_status=dream.analysis_status,
                insight=dream.one_line_insight,
                mood_on_wake=dream.mood_on_wake,
                dreamed_at=dream.dreamed_at,
                created_at=dream.created_at,
            )
            for dream in dreams
        ]

        if not nodes:
            return GraphPayload(nodes=[], edges=[])

        dream_ids = {node.id for node in nodes}
        links = (
            await self._session.scalars(
                select(DreamLink).where(
                    or_(
                        DreamLink.source_dream_id.in_(dream_ids),
                        DreamLink.target_dream_id.in_(dream_ids),
                    )
                )
            )
        ).all()

        edges = [
            GraphEdge(
                source=link.source_dream_id,
                target=link.target_dream_id,
                similarity=link.similarity,
            )
            for link in links
            if link.source_dream_id in dream_ids and link.target_dream_id in dream_ids
        ]
        return GraphPayload(nodes=nodes, edges=edges)