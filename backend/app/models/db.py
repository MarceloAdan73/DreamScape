"""Modelos SQLAlchemy 2.x (async) y fábrica de sesiones.

Decisiones de diseño:
- SQLite async vía `aiosqlite`. Sin servicios externos.
- Migraciones: `Base.metadata.create_all` al arrancar. Para este proyecto el
  esquema es estable y pequeño; Alembic se justificaría recién cuando haya
  migraciones con datos productivos que preservar (ver README).
- Los enlaces entre sueños (`dream_links`) son simétricos: se guardan siempre
  con `source_dream_id < target_dream_id` y una restricción única evita
  duplicados (A→B y B→A son la misma relación).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.config import get_settings


def utcnow() -> datetime:
    """Timestamp con zona UTC (SQLite lo persiste sin tz; se normaliza al leer)."""
    return datetime.now(UTC)


class Base(AsyncAttrs, DeclarativeBase):
    """Base declarativa con soporte async."""


class Dream(Base):
    __tablename__ = "dreams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    dreamed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    mood_on_wake: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Ciclo de vida del análisis: pending -> processing -> completed | failed
    analysis_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    one_line_insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    entity_links: Mapped[list[DreamEntity]] = relationship(
        back_populates="dream", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (Index("ix_dreams_created_at", "created_at"),)


class Entity(Base):
    """Símbolo, emoción, persona o lugar recurrente."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # symbol | emotion | person | place
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    # El nombre es la identidad de la entidad: un mismo nombre con dos tipos
    # ("ex" como símbolo y como persona) es la misma entidad, no dos.
    __table_args__ = (
        UniqueConstraint("name", name="uq_entity_name"),
        Index("ix_entities_type", "type"),
    )


class DreamEntity(Base):
    """Relación sueño ↔ entidad con peso e interpretación junguiana breve."""

    __tablename__ = "dream_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dream_id: Mapped[int] = mapped_column(
        ForeignKey("dreams.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    # Peso/relevancia de la entidad dentro del sueño (>= 0).
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    # Solo para emociones: intensidad 0-10.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    dream: Mapped[Dream] = relationship(back_populates="entity_links")
    entity: Mapped[Entity] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("dream_id", "entity_id", name="uq_dream_entity"),)


class DreamLink(Base):
    """Arista simétrica entre dos sueños similares."""

    __tablename__ = "dream_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_dream_id: Mapped[int] = mapped_column(
        ForeignKey("dreams.id", ondelete="CASCADE"), nullable=False
    )
    target_dream_id: Mapped[int] = mapped_column(
        ForeignKey("dreams.id", ondelete="CASCADE"), nullable=False
    )
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_dream_id", "target_dream_id", name="uq_dream_link"),
        Index("ix_dream_links_source", "source_dream_id"),
        Index("ix_dream_links_target", "target_dream_id"),
    )


class MonthlyLetter(Base):
    """Carta mensual del subconsciente (idempotente por mes `YYYY-MM`)."""

    __tablename__ = "monthly_letters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[str] = mapped_column(String(7), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


# --- Motor y sesiones -------------------------------------------------------

_settings = get_settings()

engine = create_async_engine(_settings.database_url, echo=False, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Crea el directorio de datos y el esquema si no existe."""
    data_dir: Path = _settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migración liviana: agrega columnas nuevas a tablas ya creadas.
        # (create_all no altera tablas existentes; Alembic no se justifica aún.)
        columns = {
            "dreams": ["title"],
        }
        for table, additions in columns.items():
            info = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
            existing = {row[1] for row in info.all()}
            for column in additions:
                if column in existing:
                    continue
                await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")

        await _migrate_entities_unique_by_name(conn)


# Especificidad del tipo: cuando un mismo nombre aparece con dos tipos gana el
# más informativo. `symbol` es el comodín, así que siempre pierde.
_TYPE_SPECIFICITY: dict[str, int] = {"symbol": 0, "emotion": 1, "place": 2, "person": 3}

# SQL de la migración de entidades: la fila superviviente de un nombre es la
# de tipo más específico (desempata por id, el más antiguo).
_SURVIVOR_ORDER = """
    ORDER BY CASE type
        WHEN 'person' THEN 3 WHEN 'place' THEN 2
        WHEN 'emotion' THEN 1 ELSE 0 END DESC,
        id ASC
    LIMIT 1
"""

# Para una fila de `dream_entities`: id de la entidad que sobrevive a su nombre.
# Se trae sus propios paréntesis para poder pegarlo en cualquier expresión.
_survivor_sql = f"""(
            SELECT e2.id FROM entities e2
            WHERE e2.name = (SELECT e.name FROM entities e WHERE e.id = dream_entities.entity_id)
            {_SURVIVOR_ORDER}
        )"""

# Entidades que pierden la fusión: no son la superviviente de su nombre.
_losers_sql = f"""
    SELECT e.id FROM entities e
    WHERE e.id NOT IN (
        SELECT e2.id FROM entities e2
        WHERE e2.name = e.name
        {_SURVIVOR_ORDER}
    )
"""


async def _migrate_entities_unique_by_name(conn: AsyncConnection) -> None:
    """One-off: `entities` pasó de UNIQUE(name, type) a UNIQUE(name).

    `create_all` no altera tablas existentes, así que a las bases viejas hay que
    fusionar a mano las entidades que comparten nombre con distinto tipo,
    reapuntando sus vínculos, y recién después imponer el índice único.
    """
    # SQLite no conserva el nombre de un constraint UNIQUE de tabla (lo llama
    # `sqlite_autoindex_*`), así que la detección va por las columnas del índice.
    indexes = await conn.exec_driver_sql("PRAGMA index_list(entities)")
    legacy = False
    for index in indexes.all():
        if not index[2]:  # no es único
            continue
        info = await conn.exec_driver_sql(f"PRAGMA index_info('{index[1]}')")
        columns = [row[2] for row in info.all()]
        if columns == ["name"]:
            return  # base ya migrada (o creada con el esquema nuevo)
        if columns == ["name", "type"]:
            legacy = True
    if not legacy:
        return

    # 1) Entidades sin ningún vínculo: no las usa nadie.
    await conn.exec_driver_sql(
        "DELETE FROM entities WHERE id NOT IN (SELECT entity_id FROM dream_entities)"
    )

    # 2) Mismo nombre, distinto tipo: sobrevive la fila con el tipo más
    #    específico y hereda los vínculos de las otras.
    #
    #    Reapuntar de golpe no sirve: SQLite valida UNIQUE(dream_id, entity_id)
    #    fila por fila y una colisión aborta el UPDATE a mitad. Va en dos pasos:
    #    primero se borran los vínculos que ya están cubiertos por el de la
    #    entidad superviviente, y recién después se reapunta el resto (para
    #    entonces cada sueño ya tiene su vínculo y no hay choque posible).
    await conn.exec_driver_sql(
        f"""
        DELETE FROM dream_entities
        WHERE entity_id IN ({_losers_sql})
          AND EXISTS (
            SELECT 1 FROM dream_entities other
            WHERE other.dream_id = dream_entities.dream_id
              AND other.id != dream_entities.id
              AND other.entity_id = {_survivor_sql}
          )
        """
    )
    await conn.exec_driver_sql(
        f"""
        UPDATE dream_entities
        SET entity_id = {_survivor_sql}
        WHERE entity_id IN ({_losers_sql})
        """
    )
    await conn.exec_driver_sql(
        """
        DELETE FROM entities
        WHERE id NOT IN (SELECT entity_id FROM dream_entities)
        """
    )

    # 3) Tabla legacy todavía con UNIQUE(name, type): solo se puede agregar el
    #    índice nuevo, no reemplazar la restricción sin recrear la tabla.
    await conn.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_entities_name ON entities(name)"
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por request."""
    async with async_session_factory() as session:
        yield session
