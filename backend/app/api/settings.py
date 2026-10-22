"""Endpoints de configuración (Settings): el usuario conecta su IA desde la UI.

Flujo estándar de este tipo de apps:
1. `GET /api/settings`         → estado efectivo (runtime + entorno, sin keys).
2. `POST /api/settings/detect` → detecta el proveedor y lista modelos.
3. `PUT /api/settings`         → guarda proveedor/modelos/key elegidos.
4. `DELETE /api/settings`      → vuelve a la configuración por defecto (.env).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core import llm as llm_module
from app.schemas.settings import RuntimeSettingsRead, RuntimeSettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


def _service() -> SettingsService:
    return SettingsService()


@router.get("", response_model=RuntimeSettingsRead)
async def get_settings() -> RuntimeSettingsRead:
    """Estado efectivo de la configuración (nunca expone API keys)."""
    return _service().read()


@router.put("", response_model=RuntimeSettingsRead)
async def update_settings(payload: RuntimeSettingsUpdate) -> RuntimeSettingsRead:
    """Guarda la configuración elegida por el usuario (persistida en `data/`)."""
    return _service().update(payload)


@router.delete("", response_model=RuntimeSettingsRead)
async def reset_settings() -> RuntimeSettingsRead:
    """Borra la config en runtime: se vuelve a la de entorno (.env)."""
    return _service().clear()


@router.post("/detect", response_model=RuntimeSettingsRead)
async def detect_settings() -> RuntimeSettingsRead:
    """Detecta el proveedor local y ajusta la config runtime a los hallazgos.

    Regla: si el proveedor activo es Ollama y responde, se actualizan los
    modelos configurados a los disponibles (chat y embed) si el actual no
    responde. No toca keys ni el proveedor elegido.
    """
    service = _service()
    current = service.read()

    if current.provider == "ollama":
        available = await _available_models()
        chat = available.get("chat", [])
        embed = available.get("embed", [])
        # Elegimos: mantener el configurado si está, sino el primero disponible.
        chat_model = current.ollama_chat_model if current.ollama_chat_model in chat else (
            chat[0] if chat else None
        )
        embed_model = current.ollama_embed_model if current.ollama_embed_model in embed else (
            embed[0] if embed else None
        )
        return _service().update(
            RuntimeSettingsUpdate(
                ollama_chat_model=chat_model,
                ollama_embed_model=embed_model,
            )
        )

    # OpenAI-compatible: detectar requiere key; solo devolvemos el estado.
    return current


@router.get("/models")
async def list_models() -> dict[str, list[str]]:
    """Lista los modelos disponibles del proveedor activo (para el selector)."""
    return await _available_models()


async def _available_models() -> dict[str, list[str]]:
    """Llama al core y traduce errores a HTTP con mensaje claro."""
    try:
        return await llm_module.list_available_models()
    except llm_module.LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No se pudieron listar los modelos: {exc}",
        ) from exc