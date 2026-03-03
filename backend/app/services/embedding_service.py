"""
Embedding Service — generates text embeddings via OpenAI text-embedding-3-small.

Used for semantic retrieval of reference examples (operator replies).
Cost: ~$0.02 per 1M tokens.
"""
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims
MAX_INPUT_CHARS = 8000  # ~2K tokens safe limit


def _get_client() -> Optional[AsyncOpenAI]:
    if not settings.OPENAI_API_KEY:
        return None
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def get_embedding(text: str) -> Optional[list[float]]:
    """Get embedding vector for a text string. Returns None if unavailable."""
    client = _get_client()
    if not client:
        logger.warning("[EMBED] OpenAI not configured, skipping embedding")
        return None
    try:
        response = await client.embeddings.create(
            input=text[:MAX_INPUT_CHARS],
            model=EMBEDDING_MODEL,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"[EMBED] Embedding failed: {e}")
        return None


async def get_embeddings_batch(texts: list[str], batch_size: int = 100) -> list[Optional[list[float]]]:
    """Batch embed multiple texts. Returns list aligned with input (None for failures)."""
    client = _get_client()
    if not client:
        logger.warning("[EMBED] OpenAI not configured, skipping batch embedding")
        return [None] * len(texts)

    all_embeddings: list[Optional[list[float]]] = []
    for i in range(0, len(texts), batch_size):
        batch = [t[:MAX_INPUT_CHARS] for t in texts[i:i + batch_size]]
        try:
            response = await client.embeddings.create(input=batch, model=EMBEDDING_MODEL)
            all_embeddings.extend([d.embedding for d in response.data])
        except Exception as e:
            logger.error(f"[EMBED] Batch {i // batch_size} failed: {e}")
            all_embeddings.extend([None] * len(batch))

    return all_embeddings
