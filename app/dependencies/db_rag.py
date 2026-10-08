from fastapi import Depends

from app.dependencies.vector_store import get_chroma_client
from app.dependencies.embeddings import get_embedding_service
from app.dependencies.agent import get_agent_service


def get_db_rag_retrieval_service(
    chroma_client=Depends(get_chroma_client),
    embedding_service=Depends(get_embedding_service),
    agent_service=Depends(get_agent_service),
):
    """Dependency injection for DBRagRetrievalService."""
    # Local import avoids circular imports (dependencies ↔ db_rag services).
    from app.services.db_rag_retrieval_service import DBRagRetrievalService

    return DBRagRetrievalService(
        chroma_client=chroma_client,
        embedding_service=embedding_service,
        agent_service=agent_service,
    )


def get_db_rag_query_service(
    agent_service=Depends(get_agent_service),
):
    """Dependency injection for DBRagQueryService."""
    from app.services.db_rag_query_service import DBRagQueryService

    return DBRagQueryService(agent_service=agent_service)