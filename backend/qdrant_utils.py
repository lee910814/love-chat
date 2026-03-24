import os
import uuid
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, PayloadSchemaType

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "love_counseling"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

_openai: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai


def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


async def ensure_collection(client: AsyncQdrantClient) -> None:
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION_NAME not in names:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
    await client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="category",
        field_schema=PayloadSchemaType.KEYWORD,
    )


async def embed_text(text: str) -> list[float]:
    response = await _get_openai().embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


async def upsert_documents(client: AsyncQdrantClient, documents: list[dict]) -> None:
    """documents: [{text, metadata: {source, channel, chunk_index}}]"""
    points = []
    for doc in documents:
        vector = await embed_text(doc["text"])
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"text": doc["text"], **doc.get("metadata", {})},
            )
        )
    await client.upsert(collection_name=COLLECTION_NAME, points=points)


async def search_similar(
    client: AsyncQdrantClient,
    query: str,
    top_k: int = 5,
    category: str | None = None,
) -> list[dict]:
    query_vector = await embed_text(query)
    query_filter = (
        Filter(must=[FieldCondition(key="category", match=MatchValue(value=category))])
        if category
        else None
    )
    results = await client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True,
        query_filter=query_filter,
    )
    return [
        {
            "text": r.payload.get("text", ""),
            "source": r.payload.get("source", ""),
            "channel": r.payload.get("channel", "알 수 없는 채널"),
            "category": r.payload.get("category", "기타"),
            "score": r.score,
        }
        for r in results
    ]
