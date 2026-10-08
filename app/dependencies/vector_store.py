from fastapi import Depends
from app.vector_db.chroma_client import ChromaClient
from app.config.setting import settings

VECTOR_STORE_DISTANCE_SPACE = settings.VECTOR_STORE_DISTANCE_SPACE


def get_chroma_client() -> ChromaClient:
    return ChromaClient()


def get_collection(feature_id: int):
    """Get or create the ChromaDB collection for a feature's direct documents."""
    collection_name = f"feature_{feature_id}"
    return get_collection_by_name(collection_name)


def get_item_collection(item_id: str):
    """Get or create the ChromaDB collection for a classroom item's documents."""
    collection_name = f"item_{item_id}"
    return get_collection_by_name(collection_name)


def get_collection_by_name(collection_name: str):
    """Get or create a ChromaDB collection by its exact name."""
    chroma_client = ChromaClient()
    collection = chroma_client.client.get_or_create_collection(
        name=collection_name, metadata={"hnsw:space": VECTOR_STORE_DISTANCE_SPACE}
    )
    _ensure_collection_space(collection)
    return collection


def _ensure_collection_space(collection) -> None:
    metadata = getattr(collection, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}

    space = metadata.get("hnsw:space")
    if space != VECTOR_STORE_DISTANCE_SPACE:
        raise RuntimeError(
            "Vector store collection distance space mismatch. "
            f"Expected '{VECTOR_STORE_DISTANCE_SPACE}', got '{space}'. "
            "Please delete and reindex the collection."
        )
