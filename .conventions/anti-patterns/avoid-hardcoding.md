# Anti-Pattern: Hardcoded Values

## BAD

```python
async def get_embedding(text: str) -> list[float]:
    resp = await httpx.post(
        "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding",
        headers={"Authorization": "Bearer AQVN1234secret"},
        json={"modelUri": "emb://b1g.../text-search-doc/latest", "text": text},
    )
    return resp.json()["embedding"]
```

## GOOD

```python
from config.settings import get_settings

async def get_embedding(text: str) -> list[float]:
    settings = get_settings()
    resp = await httpx.post(
        settings.yc_embeddings_url,
        headers={"Authorization": f"Bearer {settings.yc_api_key}"},
        json={"modelUri": settings.embed_doc_model, "text": text},
    )
    return resp.json()["embedding"]
```

## Rule
All URLs, API keys, model URIs, folder IDs, and tunable thresholds must come from
`Settings` (loaded from `.env`). The only place hardcoded defaults are acceptable
is inside `Settings` field definitions with `Field(default=...)`.
