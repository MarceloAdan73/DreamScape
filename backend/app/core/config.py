"""Configuración central de DreamScape.

Toda la configuración entra por variables de entorno (y opcionalmente un archivo
`.env`). Nunca se hardcodean secretos ni rutas absolutas de máquina.

La regla de oro de privacidad se refleja acá: el proveedor por defecto es
`ollama` (100% local) y el fallback a la nube (`openai`) es explícito.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/  ->  app/core/config.py retrocede dos niveles.
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configuración tipada cargada desde el entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicación ---------------------------------------------------------
    app_name: str = "DreamScape"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    debug: bool = False

    # Orígenes permitidos por CORS (el frontend de Vite por defecto).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Base de datos ------------------------------------------------------
    # SQLite async por defecto. Ruta relativa al backend.
    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data' / 'dreamscape.db').as_posix()}"

    # --- Proveedor de IA ----------------------------------------------------
    # "ollama" = local (privacidad total, default). "openai" = compatible nube.
    llm_provider: Literal["ollama", "openai"] = "ollama"
    # 10 min: una extracción larga en CPU puede pasar fácil los 5 min y, al
    # cortarse a mitad, el sueño queda `failed` y no cuenta para los patrones.
    llm_timeout_seconds: float = 600.0
    llm_max_retries: int = 2
    llm_temperature: float = 0.7

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"

    # OpenAI-compatible (OpenAI, Groq, Together, etc.)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    # --- ChromaDB (vector store embebido) -----------------------------------
    chroma_path: str = (BACKEND_DIR / "data" / "chroma").as_posix()
    chroma_collection: str = "dreams"

    # --- Similitud entre sueños --------------------------------------------
    # Distancia máxima en Chroma para considerar dos sueños "similares".
    similarity_threshold: float = 0.45
    similar_top_k: int = 5

    @property
    def data_dir(self) -> Path:
        """Directorio de datos (DB y Chroma). Se crea on-demand."""
        return BACKEND_DIR / "data"


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración (cacheada) como dependencia inyectable."""
    return Settings()
