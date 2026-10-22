"""Servicio de Settings: mezcla runtime (UI) + entorno y resuelve lo efectivo.

El frontend lee/escribe estos valores vía HTTP. La API key solo viaja en el
`PUT`; al leer se devuelve `openai_api_key_set`, nunca la key.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.runtime import RuntimeConfig, RuntimeStore
from app.schemas.settings import RuntimeSettingsRead, RuntimeSettingsUpdate


class SettingsService:
    """Aplica las Settings de la UI sobre la configuración de entorno."""

    def __init__(self, settings: Settings | None = None, store: RuntimeStore | None = None) -> None:
        self._settings = settings or Settings()
        self._store = store or RuntimeStore(self._settings)

    def read(self) -> RuntimeSettingsRead:
        runtime = self._store.load()
        cfg = self._settings
        source: str = "runtime"
        if (
            runtime.provider is None
            and not runtime.openai_api_key
            and not runtime.ollama_chat_model
        ):
            source = "env"
        return RuntimeSettingsRead(
            provider=runtime.provider or cfg.llm_provider,
            ollama_base_url=runtime.ollama_base_url or cfg.ollama_base_url,
            ollama_chat_model=runtime.ollama_chat_model or cfg.ollama_chat_model,
            ollama_embed_model=runtime.ollama_embed_model or cfg.ollama_embed_model,
            openai_base_url=runtime.openai_base_url or cfg.openai_base_url,
            openai_chat_model=runtime.openai_chat_model or cfg.openai_chat_model,
            openai_embed_model=runtime.openai_embed_model or cfg.openai_embed_model,
            openai_api_key_set=runtime.openai_api_key_set or bool(cfg.openai_api_key),
            source=source,
        )

    def update(self, payload: RuntimeSettingsUpdate) -> RuntimeSettingsRead:
        """Aplica el payload parcial sobre lo guardado y persiste."""
        runtime = self._store.load()

        # Solo los campos presentes (no None) modifican el estado guardado.
        updated_provider = payload.provider if payload.provider is not None else runtime.provider
        updated = RuntimeConfig(
            provider=updated_provider,
            ollama_base_url=(
                payload.ollama_base_url
                if payload.ollama_base_url is not None
                else runtime.ollama_base_url
            ),
            ollama_chat_model=(
                payload.ollama_chat_model
                if payload.ollama_chat_model is not None
                else runtime.ollama_chat_model
            ),
            ollama_embed_model=(
                payload.ollama_embed_model
                if payload.ollama_embed_model is not None
                else runtime.ollama_embed_model
            ),
            openai_base_url=(
                payload.openai_base_url
                if payload.openai_base_url is not None
                else runtime.openai_base_url
            ),
            openai_chat_model=(
                payload.openai_chat_model
                if payload.openai_chat_model is not None
                else runtime.openai_chat_model
            ),
            openai_embed_model=(
                payload.openai_embed_model
                if payload.openai_embed_model is not None
                else runtime.openai_embed_model
            ),
            openai_api_key=(
                payload.openai_api_key
                if payload.openai_api_key is not None
                else runtime.openai_api_key
            ),
        )
        self._store.save(updated)
        return self.read()

    def clear(self) -> RuntimeSettingsRead:
        """Vuelve a la configuración de entorno (borra el runtime)."""
        self._store.clear()
        return self.read()