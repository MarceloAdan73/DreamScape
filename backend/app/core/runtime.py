"""Configuración en runtime (Settings) persistida localmente.

Permite al usuario elegir proveedor, modelos y API key desde la UI, sin tocar
`.env`. Se guarda en `backend/data/runtime.json` (carpeta de datos, gitignoreada
como los sueños). La API key jamás se devuelve a la interfaz: solo se expone un
booleano `openai_api_key_set`.

Resolver: runtime (Settings de la UI) > entorno (`config.py`). El proveedor
efectivo se arma en `app/core/llm.py::get_provider`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

from app.core.config import Settings, get_settings

# ProviderName: "ollama" (local) | "openai" (nube compatible).
ProviderName = Literal["ollama", "openai"]

_RUNTIME_FILENAME = "runtime.json"


@dataclass
class RuntimeConfig:
    """Overrides del usuario. `None` = usar el default de entorno."""

    provider: ProviderName | None = None
    ollama_base_url: str | None = None
    ollama_chat_model: str | None = None
    ollama_embed_model: str | None = None
    openai_base_url: str | None = None
    openai_chat_model: str | None = None
    openai_embed_model: str | None = None
    openai_api_key: str | None = None

    @property
    def openai_api_key_set(self) -> bool:
        return bool(self.openai_api_key)


class RuntimeStore:
    """Lee/escribe la config en `data/runtime.json` (tiny, sin lock)."""

    def __init__(self, settings: Settings | None = None, path: Path | None = None) -> None:
        cfg = settings or get_settings()
        self._path = path or cfg.data_dir / _RUNTIME_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> RuntimeConfig:
        """Devuelve la config guardada; si falta/está corrupta, una vacía."""
        if not self._path.exists():
            return RuntimeConfig()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return RuntimeConfig()
        if not isinstance(data, dict):
            return RuntimeConfig()
        allowed = {f.name for f in fields(RuntimeConfig)}
        kwargs = {key: data[key] for key in data if key in allowed}
        return RuntimeConfig(**kwargs)

    def save(self, config: RuntimeConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(vars(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


def current_runtime() -> RuntimeConfig:
    """Config runtime persistida en disco (data/runtime.json)."""
    return RuntimeStore().load()