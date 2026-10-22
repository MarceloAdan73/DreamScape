# DreamScape Backend

API FastAPI del diario de sueños: CRUD, análisis por IA (LLMProvider dual
Ollama/OpenAI-compatible), grafo, patrones y similitud (ChromaDB embebido).

```bash
python -m pip install -e ".[dev,ai]"
uvicorn app.main:app --reload --port 8000
pytest
```

Documentación completa en el [README de la raíz](../README.md).
