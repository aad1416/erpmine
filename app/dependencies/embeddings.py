from app.services.embedding_service import EmbeddingService, embedding_service


def get_embedding_service() -> EmbeddingService:
    """
    Dependency injection for Embedding Service

    Returns singleton instance of EmbeddingService
    """
    return embedding_service
