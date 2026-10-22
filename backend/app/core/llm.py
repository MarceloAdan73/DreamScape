"""Proveedor de IA dual: Ollama (local) ↔ OpenAI-compatible (nube).

Interfaz única `LLMProvider` con dos implementaciones reales y una fábrica.
La resolución es por configuración (`LLM_PROVIDER`):
1. `ollama` (default) — 100% local, sin nube. Regla de oro de privacidad.
2. `openai` — API compatible (OpenAI, Groq, Together, etc.). Solo cuando se
   define explícitamente `LLM_PROVIDER=openai` y una API key.

Si Ollama no responde, el análisis se marca como `failed` con un mensaje claro
y se loguea; nunca se cae en silencio (ver `app/services/analyzer.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.runtime import RuntimeConfig

# Tiempo acotado para el health-check (no debe colgar el status endpoint).
_HEALTH_TIMEOUT_SECONDS = 8.0

ChatMessage = dict[str, str]


class LLMError(RuntimeError):
    """Base de errores de capa IA."""


class ProviderUnavailable(LLMError):
    """No se pudo conectar con el proveedor (red/offline)."""


class ProviderConfigError(LLMError):
    """Configuración inválida del proveedor (ej. falta API key)."""


class ProviderResponseError(LLMError):
    """El proveedor respondió un error HTTP o una forma inesperada."""


@dataclass(frozen=True)
class ProviderStatus:
    """Resultado del health-check de un proveedor."""

    provider: str
    ok: bool
    detail: str


class LLMProvider(Protocol):
    """Contrato único para chat y embeddings."""

    name: str

    async def chat(
        self,
        messages: list[ChatMessage],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def health(self) -> tuple[bool, str]: ...


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


class OllamaProvider:
    """Cliente HTTP para el servidor local de Ollama (sin nube)."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embed_model: str,
        timeout: float,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.timeout = timeout

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        timeout: float,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.post(f"{self.base_url}{path}", json=payload)
        except httpx.ConnectError as exc:
            raise ProviderUnavailable(
                f"No se pudo conectar con Ollama en {self.base_url}. "
                "¿Está corriendo `ollama serve`?"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Error HTTP hacia Ollama: {exc}") from exc

    async def chat(
        self,
        messages: list[ChatMessage],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        if temperature is not None:
            payload["temperature"] = temperature

        response = await self._post("/api/chat", payload, self.timeout)
        if response.status_code != 200:
            raise ProviderResponseError(
                f"Ollama respondió {response.status_code}: {response.text[:400]}"
            )
        data = response.json()
        content = data.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("Ollama no devolvió contenido en /api/chat.")
        return content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._post(
            "/api/embed",
            {"model": self.embed_model, "input": texts},
            self.timeout,
        )
        if response.status_code != 200:
            raise ProviderResponseError(
                f"Ollama respondió {response.status_code} en /api/embed: {response.text[:400]}"
            )
        embeddings = response.json().get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ProviderResponseError("Ollama devolvió embeddings con forma inesperada.")
        return embeddings

    async def health(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{self.base_url}/api/tags")
        except httpx.HTTPError as exc:
            return False, f"Ollama no contesta en {self.base_url}: {exc}"
        if response.status_code != 200:
            return False, f"Ollama respondió {response.status_code} en /api/tags."
        models = response.json().get("models", [])
        names: set[str] = set()
        for entry in models:
            if isinstance(entry, dict):
                value = entry.get("name")
                if isinstance(value, str):
                    names.add(value)
        has_chat = any(self.chat_model in name for name in names)
        has_embed = any(self.embed_model in name for name in names)
        missing = [
            model
            for model, present in ((self.chat_model, has_chat), (self.embed_model, has_embed))
            if not present
        ]
        if missing:
            return (
                False,
                f"Ollama responde pero faltan modelos: {', '.join(missing)}. "
                "Ejecutá: `ollama pull " + self.embed_model + "` (y sim. con el chat).",
            )
        return True, f"Ollama respondiendo con {len(names)} modelos (requeridos presentes)."


class OpenAIProvider:
    """Cliente HTTP para APIs OpenAI-compatible (nube, fallback explícito)."""

    name = "openai"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str,
        embed_model: str,
        timeout: float,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def chat(
        self,
        messages: list[ChatMessage],
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                # Algún modelo compatible no acepta response_format: reintenta sin él.
                if response.status_code == 400 and json_mode and "response_format" in payload:
                    payload.pop("response_format", None)
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
        except httpx.ConnectError as exc:
            raise ProviderUnavailable(f"No se pudo conectar con {self.base_url}.") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Error HTTP hacia {self.base_url}: {exc}") from exc

        if response.status_code != 200:
            raise ProviderResponseError(
                f"OpenAI-compatible respondió {response.status_code}: {response.text[:400]}"
            )
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError("Respuesta de chat con forma inesperada.") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("El proveedor devolvió un contenido vacío.")
        return content

    async def embed(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"model": self.embed_model, "input": texts}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Error HTTP hacia {self.base_url}: {exc}") from exc
        if response.status_code != 200:
            raise ProviderResponseError(
                f"OpenAI-compatible respondió {response.status_code}: {response.text[:400]}"
            )
        items = response.json().get("data", [])
        items_sorted = sorted(items, key=lambda item: item.get("index", 0))
        embeddings: list[list[float]] = []
        for item in items_sorted:
            if not isinstance(item, dict):
                continue
            vector = item.get("embedding")
            if isinstance(vector, list):
                embeddings.append([float(value) for value in vector])
        if len(embeddings) != len(texts):
            raise ProviderResponseError("Embeddings con forma inesperada.")
        return embeddings

    async def health(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
        except httpx.HTTPError as exc:
            return False, f"No se pudo validar la API en {self.base_url}: {exc}"
        if response.status_code != 200:
            return False, f"La API respondió {response.status_code} (¿API key inválida?)."
        return True, "API compatible respondiendo (fallback explícito a la nube)."


def get_provider(
    settings: Settings | None = None,
    runtime: RuntimeConfig | None = None,
) -> LLMProvider:
    """Resuelve el proveedor según entorno + overrides de runtime (UI).

    Orden de precedencia: `RuntimeConfig` (Settings de la UI) > entorno.
    Default: Ollama local (regla de oro de privacidad).
    """
    cfg = settings or get_settings()
    rtc = runtime or RuntimeConfig()
    provider_name = rtc.provider or cfg.llm_provider

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=rtc.ollama_base_url or cfg.ollama_base_url,
            chat_model=rtc.ollama_chat_model or cfg.ollama_chat_model,
            embed_model=rtc.ollama_embed_model or cfg.ollama_embed_model,
            timeout=cfg.llm_timeout_seconds,
        )
    if provider_name == "openai":
        api_key = rtc.openai_api_key or cfg.openai_api_key
        if not api_key:
            raise ProviderConfigError("Se configuró el proveedor 'openai' pero no hay API key.")
        return OpenAIProvider(
            base_url=rtc.openai_base_url or cfg.openai_base_url,
            api_key=api_key,
            chat_model=rtc.openai_chat_model or cfg.openai_chat_model,
            embed_model=rtc.openai_embed_model or cfg.openai_embed_model,
            timeout=cfg.llm_timeout_seconds,
        )
    raise ProviderConfigError(f"LLM_PROVIDER desconocido: {provider_name!r}")


async def provider_status(
    settings: Settings | None = None,
    runtime: RuntimeConfig | None = None,
) -> ProviderStatus:
    """Health-check del proveedor activo (no lanza: devuelve estado)."""
    cfg = settings or get_settings()
    try:
        provider = get_provider(cfg, runtime)
    except ProviderConfigError as exc:
        return ProviderStatus(
            provider=runtime.provider if runtime and runtime.provider else cfg.llm_provider,
            ok=False,
            detail=str(exc),
        )
    try:
        ok, detail = await provider.health()
    except LLMError as exc:
        return ProviderStatus(provider=provider.name, ok=False, detail=str(exc))
    return ProviderStatus(provider=provider.name, ok=ok, detail=detail)


async def list_available_models(
    settings: Settings | None = None,
    runtime: RuntimeConfig | None = None,
) -> dict[str, list[str]]:
    """Lista los modelos disponibles del proveedor activo (para el selector UI).

    Ante cualquier fallo devuelve `{}` (la UI muestra el error vía
    `provider_status`, que sí explica la causa).
    """
    cfg = settings or get_settings()
    rtc = runtime or RuntimeConfig()
    provider_name = rtc.provider or cfg.llm_provider
    try:
        provider = get_provider(cfg, rtc)
    except ProviderConfigError:
        return {}

    if isinstance(provider, OllamaProvider):
        return await _list_ollama_models(provider)
    if isinstance(provider, OpenAIProvider):
        return await _list_openai_models(provider)
    raise LLMError(f"No sé listar modelos del proveedor {provider_name!r}.")


async def _list_ollama_models(provider: OllamaProvider) -> dict[str, list[str]]:
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{provider.base_url}/api/tags")
    except httpx.HTTPError as exc:
        raise ProviderUnavailable(
            f"Ollama no contesta en {provider.base_url}: {exc}"
        ) from exc
    if response.status_code != 200:
        raise ProviderResponseError(
            f"Ollama respondió {response.status_code} en /api/tags."
        )
    models: list[str] = []
    for entry in response.json().get("models", []):
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            name = entry["name"]
            # "nomic-embed-text:latest" → "nomic-embed-text" (el registro los da
            # con :latest; config.py y la UI usan el nombre sin tag).
            if name.endswith(":latest"):
                name = name[: -len(":latest")]
            models.append(name)
    # nomic-embed-text / *-embed → embedding; el resto, chat.
    embed = sorted(m for m in models if "embed" in m)
    chat = sorted(m for m in models if "embed" not in m)
    # Preferir modelos de chat generales antes que los "coder/tool" al
    # auto-detectar: así detección elige qwen3.5:9b antes que qwen2.5-coder.
    chat.sort(key=lambda name: any(tag in name for tag in ("coder", "tool", "math")))
    return {"chat": chat, "embed": embed}


async def _list_openai_models(provider: OpenAIProvider) -> dict[str, list[str]]:
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{provider.base_url}/models",
                headers=provider._headers(),
            )
    except httpx.HTTPError as exc:
        raise ProviderUnavailable(
            f"No se pudo listar los modelos en {provider.base_url}: {exc}"
        ) from exc
    if response.status_code != 200:
        raise ProviderResponseError(
            f"La API respondió {response.status_code} al listar modelos."
        )
    data = response.json().get("data", [])
    models: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str):
            models.append(model_id)
    # Indistinguible sin llamadas: se sugieren modelos chat por heurística.
    chat = sorted(m for m in models if "embedding" not in m)
    embed = sorted(m for m in models if "embedding" in m)
    return {"chat": chat, "embed": embed}
