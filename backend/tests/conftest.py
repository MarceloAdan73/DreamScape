"""Configuración de pytest y fixtures compartidas."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from app.core.config import get_settings
from app.core.runtime import RuntimeConfig
from app.main import app
from app.models import db as db_module
from app.models.db import Base, get_session
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path: Path, monkeypatch) -> AsyncIterator[AsyncClient]:
    """Cliente HTTP contra la app con base y Chroma aislados por test."""
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # El orquestador de análisis abre sus propias sesiones desde el factory del
    # módulo de DB; lo apuntamos a la base temporal del test.
    monkeypatch.setattr(db_module, "async_session_factory", session_factory)

    # Croma aislado por test (lo usa el pipeline de análisis).
    settings = get_settings()
    monkeypatch.setattr(settings, "chroma_path", str(tmp_path / "chroma"))

    # Runtime aislado por test: los análisis no deben leer data/runtime.json
    # real del desarrollador (lo persiste la UI de Settings).
    from app.api import analysis as analysis_api
    from app.services import analyzer as analyzer_service

    monkeypatch.setattr(
        analysis_api, "current_runtime", lambda: RuntimeConfig()
    )
    monkeypatch.setattr(
        analyzer_service, "current_runtime", lambda: RuntimeConfig()
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await engine.dispose()
