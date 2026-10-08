from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session
from app.services.chat_service import ChatService
from app.services.admin_chat_service import AdminChatService
from app.services.memory_service import MemoryService
from app.services.persona_service import PersonaService
from app.services.rag_service import RAGService
from app.services.agent_service import AgentService
from app.services.embedding_service import EmbeddingService
from app.repositories.lyndom_db import LyndomDBRepository
from app.repositories.chats import ChatRepository
from app.repositories.messages import MessageRepository
from app.repositories.personas import PersonaRepository
from app.repositories.feature_classrooms import FeatureClassroomRepository
from app.repositories.classroom_item_assignments import (
    ClassroomItemAssignmentRepository,
)
from app.dependencies.database import get_db
from app.dependencies.embeddings import get_embedding_service
from app.dependencies.vector_store import get_chroma_client
from app.dependencies.agent import get_agent_service
from app.dependencies.db_rag import (
    get_db_rag_retrieval_service,
    get_db_rag_query_service,
)
from app.dependencies.lyndom_db import get_lyndom_db_optional
from app.dependencies.files import get_files_service
from app.services.chat_agent_runner import ChatAgentRunner
from app.services.chat_agent_service import ChatAgentService
from app.services.admin_chat_agent_runner import AdminChatAgentRunner
from app.services.admin_chat_agent_service import AdminChatAgentService
from app.services.database_query_tool_service import DatabaseQueryToolService
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService
from app.services.db_rag_retrieval_service import DBRagRetrievalService
from app.services.db_rag_query_service import DBRagQueryService
from app.services.files import FilesService
from app.services.reports_agent_runner import ReportsAgentRunner



def get_memory_service(db: Session = Depends(get_db)) -> MemoryService:
    """
    Dependency injection for Memory Service
    """
    chat_repository = ChatRepository(db)
    message_repository = MessageRepository(db)
    return MemoryService(chat_repository, message_repository)


def get_persona_service(db: Session = Depends(get_db)) -> PersonaService:
    """
    Dependency injection for Persona Service
    """
    persona_repository = PersonaRepository(db)
    return PersonaService(persona_repository)


def get_rag_service(
    db: Session = Depends(get_db),
    chroma_client=Depends(get_chroma_client),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> RAGService:
    """
    Dependency injection for RAG Service
    """
    feature_classroom_repo = FeatureClassroomRepository(db)
    item_assignment_repo = ClassroomItemAssignmentRepository(db)
    return RAGService(
        chroma_client,
        embedding_service,
        feature_classroom_repo,
        item_assignment_repo,
    )


def get_chat_service(
    memory_service: MemoryService = Depends(get_memory_service),
    persona_service: PersonaService = Depends(get_persona_service),
    rag_service: RAGService = Depends(get_rag_service),
    agent_service: AgentService = Depends(get_agent_service),
    db: Session = Depends(get_db),
    db_rag_retrieval_service: DBRagRetrievalService = Depends(get_db_rag_retrieval_service),
    db_rag_query_service: DBRagQueryService = Depends(get_db_rag_query_service),
) -> ChatService:
    """
    Dependency injection for Chat Service

    Injects all required services:
    - MemoryService (chat history)
    - PersonaService (persona retrieval)
    - RAGService (data retrieval)
    - AgentService (LLM generation)
    - DB-RAG optional extended paths
    """
    return ChatService(
        memory_service=memory_service,
        persona_service=persona_service,
        rag_service=rag_service,
        agent_service=agent_service,
        db_rag_retrieval_service=db_rag_retrieval_service,
        db_rag_query_service=db_rag_query_service,
        db_session_factory=lambda: db,
    )


_chat_agent_runner_singleton: ChatAgentRunner | None = None


def get_chat_agent_runner() -> ChatAgentRunner:
    global _chat_agent_runner_singleton
    if _chat_agent_runner_singleton is None:
        _chat_agent_runner_singleton = ChatAgentRunner()
    return _chat_agent_runner_singleton


def get_document_retrieval_tool_service(
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentRetrievalToolService:
    """
    Dependency injection for the shared document retrieval tool service
    (retrieve_documents agent tool).
    """
    return DocumentRetrievalToolService(rag_service=rag_service)


def get_database_query_tool_service(
    db_rag_retrieval_service: DBRagRetrievalService = Depends(get_db_rag_retrieval_service),
    db_rag_query_service: DBRagQueryService = Depends(get_db_rag_query_service),
    lyndom_repo: Optional[LyndomDBRepository] = Depends(get_lyndom_db_optional),
) -> DatabaseQueryToolService:
    """
    Dependency injection for the shared database query tool service
    (query_database agent tool).
    """
    return DatabaseQueryToolService(
        db_rag_retrieval_service=db_rag_retrieval_service,
        db_rag_query_service=db_rag_query_service,
        lyndom_repo=lyndom_repo,
    )


_reports_agent_runner_singleton: ReportsAgentRunner | None = None


def get_reports_agent_runner() -> ReportsAgentRunner:
    global _reports_agent_runner_singleton
    if _reports_agent_runner_singleton is None:
        _reports_agent_runner_singleton = ReportsAgentRunner()
    return _reports_agent_runner_singleton


def get_chat_agent_service(
    memory_service: MemoryService = Depends(get_memory_service),
    persona_service: PersonaService = Depends(get_persona_service),
    rag_service: RAGService = Depends(get_rag_service),
    agent_service: AgentService = Depends(get_agent_service),
    db: Session = Depends(get_db),
    db_rag_retrieval_service: DBRagRetrievalService = Depends(get_db_rag_retrieval_service),
    db_rag_query_service: DBRagQueryService = Depends(get_db_rag_query_service),
    chat_agent_runner: ChatAgentRunner = Depends(get_chat_agent_runner),
    document_retrieval_tool_service: DocumentRetrievalToolService = Depends(
        get_document_retrieval_tool_service
    ),
    database_query_tool_service: DatabaseQueryToolService = Depends(
        get_database_query_tool_service
    ),
    reports_agent_runner: ReportsAgentRunner = Depends(get_reports_agent_runner),
    files_service: FilesService = Depends(get_files_service),
) -> ChatAgentService:
    """
    OpenAI Agents SDK chat path with tools; delegates to legacy ChatService for non-OpenAI models.
    A `reports` Feature (Feature.entity_id == "reports") dispatches to ReportsAgentRunner instead.
    """
    legacy_chat = ChatService(
        memory_service=memory_service,
        persona_service=persona_service,
        rag_service=rag_service,
        agent_service=agent_service,
        db_rag_retrieval_service=db_rag_retrieval_service,
        db_rag_query_service=db_rag_query_service,
        db_session_factory=lambda: db,
    )
    return ChatAgentService(
        memory_service=memory_service,
        persona_service=persona_service,
        legacy_chat_service=legacy_chat,
        chat_agent_runner=chat_agent_runner,
        document_retrieval_tool_service=document_retrieval_tool_service,
        database_query_tool_service=database_query_tool_service,
        db_session_factory=lambda: db,
        reports_agent_runner=reports_agent_runner,
        files_service=files_service,
    )


def get_admin_chat_service(
    memory_service: MemoryService = Depends(get_memory_service),
    persona_service: PersonaService = Depends(get_persona_service),
    rag_service: RAGService = Depends(get_rag_service),
    agent_service: AgentService = Depends(get_agent_service),
) -> AdminChatService:
    """
    Dependency injection for Admin Chat Service

    Injects all required services:
    - MemoryService (chat history)
    - PersonaService (persona retrieval and updates)
    - RAGService (data retrieval)
    - AgentService (LLM generation for 3-step orchestration)
    """
    return AdminChatService(
        memory_service=memory_service,
        persona_service=persona_service,
        rag_service=rag_service,
        agent_service=agent_service,
    )


_admin_chat_agent_runner_singleton: AdminChatAgentRunner | None = None


def get_admin_chat_agent_runner() -> AdminChatAgentRunner:
    global _admin_chat_agent_runner_singleton
    if _admin_chat_agent_runner_singleton is None:
        _admin_chat_agent_runner_singleton = AdminChatAgentRunner()
    return _admin_chat_agent_runner_singleton


def get_admin_chat_agent_service(
    memory_service: MemoryService = Depends(get_memory_service),
    persona_service: PersonaService = Depends(get_persona_service),
    db: Session = Depends(get_db),
    legacy_admin_chat_service: AdminChatService = Depends(get_admin_chat_service),
    admin_chat_agent_runner: AdminChatAgentRunner = Depends(get_admin_chat_agent_runner),
    document_retrieval_tool_service: DocumentRetrievalToolService = Depends(
        get_document_retrieval_tool_service
    ),
    database_query_tool_service: DatabaseQueryToolService = Depends(
        get_database_query_tool_service
    ),
    reports_agent_runner: ReportsAgentRunner = Depends(get_reports_agent_runner),
    files_service: FilesService = Depends(get_files_service),
) -> AdminChatAgentService:
    """
    OpenAI Agents SDK admin chat path with tools (update_persona, retrieve_documents,
    query_database); delegates to legacy AdminChatService for non-OpenAI models.
    A `reports` Feature (Feature.entity_id == "reports") dispatches to ReportsAgentRunner instead.
    """
    return AdminChatAgentService(
        memory_service=memory_service,
        persona_service=persona_service,
        legacy_admin_chat_service=legacy_admin_chat_service,
        admin_chat_agent_runner=admin_chat_agent_runner,
        document_retrieval_tool_service=document_retrieval_tool_service,
        database_query_tool_service=database_query_tool_service,
        db_session_factory=lambda: db,
        reports_agent_runner=reports_agent_runner,
        files_service=files_service,
    )
