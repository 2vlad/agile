import asyncio
import logging

from config.settings import get_settings
from db.repositories import ChunkRepo, SearchResult
from yandex.ai_studio import YandexAIStudio

logger = logging.getLogger(__name__)


def _build_ai_client() -> YandexAIStudio:
    settings = get_settings()
    return YandexAIStudio(
        api_key=settings.yc_api_key,
        folder_id=settings.yc_folder_id,
        llm_model=settings.llm_model,
        embed_doc_model=settings.embed_doc_model,
        embed_query_model=settings.embed_query_model,
        llm_base_url=settings.yc_llm_base_url,
        embeddings_url=settings.yc_embeddings_url,
    )


def _merge_results(
    vector_results: list[SearchResult], fulltext_results: list[SearchResult]
) -> list[SearchResult]:
    """Deduplicate by chunk_id, keeping the higher score."""
    seen: dict[str, SearchResult] = {}
    for r in vector_results:
        seen[r.chunk_id] = r
    for r in fulltext_results:
        if r.chunk_id not in seen or r.score > seen[r.chunk_id].score:
            seen[r.chunk_id] = r
    return sorted(seen.values(), key=lambda r: r.score, reverse=True)


async def search_corpus(
    query: str,
    n_results: int = 5,
    ai_client: YandexAIStudio | None = None,
) -> list[dict]:
    """Hybrid vector + fulltext search with context expansion."""
    settings = get_settings()
    n_results = min(n_results, settings.max_search_results)
    own_client = False
    if ai_client is None:
        ai_client = _build_ai_client()
        own_client = True

    try:
        embedding = await ai_client.get_embedding(query, for_query=True)

        chunk_repo = ChunkRepo()
        vector_results, fulltext_results = await asyncio.gather(
            chunk_repo.search_vector(embedding, n_results),
            chunk_repo.search_fulltext(query, n_results),
        )

        merged = _merge_results(vector_results, fulltext_results)
        logger.info(
            "Search: %d vector + %d fulltext -> %d merged results",
            len(vector_results),
            len(fulltext_results),
            len(merged),
        )

        passages = await asyncio.gather(
            *(chunk_repo.get_passage(r.doc_id, r.chunk_index, radius=settings.context_radius)
              for r in merged)
        )

        results: list[dict] = []
        for r, passage_chunks in zip(merged, passages):
            expanded_text = "\n\n".join(ch["text"] for ch in passage_chunks)
            results.append(
                {
                    "chunk_id": r.chunk_id,
                    "doc_id": r.doc_id,
                    "chunk_index": r.chunk_index,
                    "text": r.text,
                    "expanded_text": expanded_text,
                    "score": r.score,
                }
            )
        return results
    finally:
        if own_client:
            await ai_client.close()


async def get_passage(
    doc_id: str,
    chunk_index: int,
    radius: int = 3,
) -> dict:
    """Fetch a passage of neighboring chunks around a given chunk index."""
    chunk_repo = ChunkRepo()
    passage_chunks = await chunk_repo.get_passage(doc_id, chunk_index, radius=radius)
    if not passage_chunks:
        logger.warning(
            "No chunks found for doc_id=%s chunk_index=%d radius=%d",
            doc_id, chunk_index, radius,
        )
    joined_text = "\n\n".join(ch["text"] for ch in passage_chunks)
    metadata = passage_chunks[0]["metadata"] if passage_chunks else {}
    return {
        "doc_id": doc_id,
        "chunk_index": chunk_index,
        "text": joined_text,
        "metadata": metadata,
    }


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": (
                "Search the document corpus using hybrid vector and fulltext search. "
                "Returns relevant passages with expanded context from neighboring chunks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query text.",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_passage",
            "description": (
                "Retrieve a passage of text from a document, centered on a specific chunk "
                "with surrounding context chunks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": "The document ID to fetch the passage from.",
                    },
                    "chunk_index": {
                        "type": "integer",
                        "description": "The central chunk index for the passage.",
                    },
                    "radius": {
                        "type": "integer",
                        "description": "Number of chunks before and after to include.",
                        "default": 3,
                    },
                },
                "required": ["doc_id", "chunk_index"],
            },
        },
    },
]
