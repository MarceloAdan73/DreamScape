"""Tests de Settings: persistencia runtime, no-exposición de keys y detect."""

from __future__ import annotations

import pytest
from app.api import settings as settings_api
from app.core import llm as llm_module
from app.core.config import get_settings
from app.core.runtime import RuntimeConfig, RuntimeStore
from app.main import app
from app.schemas.settings import RuntimeSettingsUpdate
from app.services.settings_service import SettingsService
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def runtime_store(tmp_path) -> RuntimeStore:
    return RuntimeStore(get_settings(), path=tmp_path / "runtime.json")


@pytest.fixture
def service(runtime_store: RuntimeStore) -> SettingsService:
    return SettingsService(get_settings(), store=runtime_store)


def test_runtime_store_roundtrip(runtime_store: RuntimeStore) -> None:
    config = RuntimeConfig(
        provider="openai",
        openai_api_key="sk-secreta",
        openai_chat_model="gpt-4o-mini",
    )
    runtime_store.save(config)
    loaded = runtime_store.load()
    assert loaded.provider == "openai"
    assert loaded.openai_api_key == "sk-secreta"


def test_runtime_store_load_missing_returns_empty(runtime_store: RuntimeStore) -> None:
    loaded = runtime_store.load()
    assert loaded == RuntimeConfig()


def test_settings_read_does_not_expose_key(service: SettingsService) -> None:
    service.update(
        RuntimeSettingsUpdate(
            provider="openai",
            openai_api_key="sk-muy-secreta",
            openai_base_url="https://api.groq.com/openai/v1",
        )
    )
    read = service.read()
    assert read.provider == "openai"
    assert read.openai_api_key_set is True
    # El campo real de la key no existe en la salida leída.
    assert "openai_api_key" not in read.model_dump()


def test_settings_read_uses_env_defaults_without_runtime(service: SettingsService) -> None:
    read = service.read()
    assert read.provider == "ollama"
    assert read.ollama_base_url == get_settings().ollama_base_url
    assert read.openai_api_key_set is False


def test_settings_update_merges_partial(service: SettingsService) -> None:
    service.update(RuntimeSettingsUpdate(ollama_chat_model="qwen3.5:9b"))
    read = service.read()
    assert read.ollama_chat_model == "qwen3.5:9b"
    # El resto sigue con los defaults de entorno.
    assert read.ollama_embed_model == get_settings().ollama_embed_model


async def test_settings_endpoints_roundtrip(monkeypatch, tmp_path) -> None:
    store = RuntimeStore(get_settings(), path=tmp_path / "runtime.json")
    monkeypatch.setattr(
        settings_api, "_service", lambda: SettingsService(get_settings(), store=store)
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # GET inicial: proveedor por defecto, sin key.
        initial = (await client.get("/api/settings")).json()
        assert initial["provider"] == "ollama"
        assert initial["openai_api_key_set"] is False

        # PUT: guarda key y proveedor, sin exponer la key al leer.
        updated = (
            await client.put(
                "/api/settings",
                json={
                    "provider": "openai",
                    "openai_api_key": "sk-test",
                    "openai_chat_model": "llama-3.3-70b-versatile",
                },
            )
        ).json()
        assert updated["provider"] == "openai"
        assert updated["openai_api_key_set"] is True
        assert updated["openai_chat_model"] == "llama-3.3-70b-versatile"

        read_back = (await client.get("/api/settings")).json()
        assert read_back["provider"] == "openai"
        assert "openai_api_key" not in read_back

        # DELETE: vuelve a defaults.
        reset = (await client.request("DELETE", "/api/settings")).json()
        assert reset["provider"] == "ollama"
        assert reset["openai_api_key_set"] is False

    app.dependency_overrides.clear()


async def test_detect_updates_models_from_available(monkeypatch, tmp_path) -> None:
    store = RuntimeStore(get_settings(), path=tmp_path / "runtime.json")
    monkeypatch.setattr(
        settings_api, "_service", lambda: SettingsService(get_settings(), store=store)
    )

    async def fake_list_models():
        return {"chat": ["qwen3.5:9b", "llama3.1:8b"], "embed": ["nomic-embed-text"]}

    monkeypatch.setattr(llm_module, "list_available_models", fake_list_models)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # El default (llama3.1:8b) no está → detect lo cambia a un modelo disponible.
        response = await client.post("/api/settings/detect")
        assert response.status_code == 200
        body = response.json()
        assert body["ollama_chat_model"] in {"qwen3.5:9b", "llama3.1:8b"}

        # /models devuelve la lista cruda del proveedor activo.
        models = await client.get("/api/settings/models")
        assert models.status_code == 200
        assert models.json()["chat"] == ["qwen3.5:9b", "llama3.1:8b"]
        assert models.json()["embed"] == ["nomic-embed-text"]

    app.dependency_overrides.clear()


async def test_models_endpoint_503_on_llm_error(monkeypatch, tmp_path) -> None:
    store = RuntimeStore(get_settings(), path=tmp_path / "runtime.json")
    monkeypatch.setattr(
        settings_api, "_service", lambda: SettingsService(get_settings(), store=store)
    )

    async def failing_list():
        raise llm_module.ProviderResponseError("offline")

    monkeypatch.setattr(llm_module, "list_available_models", failing_list)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/settings/models")
        assert response.status_code == 503

    app.dependency_overrides.clear()