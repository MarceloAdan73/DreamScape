"""Esquemas de la configuración en runtime expuesta a la UI.

El frontend lee y escribe estos valores vía HTTP; la API key se acepta en
el `PUT` pero **jamás** se devuelve en el `GET` (solo `openai_api_key_set`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["ollama", "openai"]


class RuntimeSettingsRead(BaseModel):
    """Estado efectivo de la configuración (runtime > entorno), sin secretos."""

    model_config = ConfigDict(from_attributes=True)

    provider: ProviderName
    ollama_base_url: str
    ollama_chat_model: str
    ollama_embed_model: str
    openai_base_url: str
    openai_chat_model: str
    openai_embed_model: str
    openai_api_key_set: bool
    source: Literal["runtime", "env"] = "runtime"


class RuntimeSettingsUpdate(BaseModel):
    """Payload del PUT: solo los campos presentes se aplican (None = no tocar)."""

    provider: ProviderName | None = None
    ollama_base_url: str | None = Field(default=None, max_length=500)
    ollama_chat_model: str | None = Field(default=None, max_length=200)
    ollama_embed_model: str | None = Field(default=None, max_length=200)
    openai_base_url: str | None = Field(default=None, max_length=500)
    openai_chat_model: str | None = Field(default=None, max_length=200)
    openai_embed_model: str | None = Field(default=None, max_length=200)
    openai_api_key: str | None = Field(default=None, max_length=500)