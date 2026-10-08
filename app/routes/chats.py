from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime

from app.dependencies.auth import get_current_user
from app.dependencies.chat import (
    get_chat_agent_service,
    get_memory_service,
)
from app.dependencies.features import get_feature_service
from app.db.models.Users import User
from app.db.models.Chat import Chat
from app.services.chat_agent_service import ChatAgentService
from app.services.memory_service import MemoryService
from app.services.feature_service import FeatureService
from app.schemas.chats import (
    ChatCreate,
    ChatUpdate,
    ChatResponse,
    ChatWithMessages,
    SendMessageRequest,
    SendMessageResponse,
    MessageSource,
)

router = APIRouter()


@router.post(
    "/features/{feature_id}/chats",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["chats"],
)
def create_chat(
    feature_id: int,
    chat_data: ChatCreate,
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    Create a new chat for a feature.

    - **feature_id**: ID of the feature this chat belongs to
    - **title**: Title of the chat

    Returns the created chat.
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Create chat
    chat = memory_service.create_chat(
        user_id=current_user.id, feature_id=feature_id, title=chat_data.title
    )

    # Build response
    response = ChatResponse(
        id=chat.id,
        user_id=chat.user_id,
        feature_id=chat.feature_id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=0,
    )

    return response


@router.get(
    "/features/{feature_id}/chats", response_model=List[ChatResponse], tags=["chats"]
)
def list_chats(
    feature_id: int,
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    List all chats for a user in a specific feature.

    - **feature_id**: ID of the feature to filter chats

    Returns list of chats for the current user in the specified feature.
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Get chats
    chats = memory_service.get_chats(current_user.id, feature_id)

    # Build response
    response = []
    for chat in chats:
        response.append(
            ChatResponse(
                id=chat.id,
                user_id=chat.user_id,
                feature_id=chat.feature_id,
                title=chat.title,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                message_count=len(chat.messages) if chat.messages else 0,
            )
        )

    return response


@router.get(
    "/features/{feature_id}/chats/{chat_id}",
    response_model=ChatWithMessages,
    tags=["chats"],
)
def get_chat(
    feature_id: int,
    chat_id: int,
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    Get a specific chat with all its messages.

    - **feature_id**: ID of the feature
    - **chat_id**: ID of the chat

    Returns the chat with all messages.
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Get chat with messages
    messages = memory_service.get_chat_history(chat_id)

    # Get chat object
    chat = memory_service.get_chat_by_id(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {chat_id} not found",
        )

    # Verify chat belongs to user
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this chat",
        )

    # Verify chat belongs to feature
    if chat.feature_id != feature_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chat {chat_id} does not belong to feature {feature_id}",
        )

    # Build response
    response = ChatWithMessages(
        id=chat.id,
        user_id=chat.user_id,
        feature_id=chat.feature_id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=len(messages),
        messages=messages,
    )

    return response


@router.post(
    "/features/{feature_id}/chats/{chat_id}/messages",
    response_model=SendMessageResponse,
    tags=["chats"],
)
async def send_message(
    feature_id: int,
    chat_id: int,
    message_data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    chat_service: ChatAgentService = Depends(get_chat_agent_service),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    Send a message to a chat.

    Uses **ChatAgentService** (OpenAI Agents SDK with optional `retrieve_documents` and
    `query_database` tools) for OpenAI models; **ChatService** fallback for other providers.

    - **use_rag**: Exposes the document retrieval tool (Agents path) or eager RAG (legacy).
    - **use_db**: Allows the database SQL tool (Agents path only; requires Lyndom DB and `DB_RAG_ENABLED`).
    - **rag_top_k**: Top‑k chunks when retrieval runs.

    Returns the assistant's response with sources, optional DB audit, and message IDs.
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Validate chat exists and belongs to user
    chat = memory_service.get_chat_by_id(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {chat_id} not found",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this chat",
        )

    if chat.feature_id != feature_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chat {chat_id} does not belong to feature {feature_id}",
        )

    # Process message via ChatAgentService (OpenAI Agents tools or legacy fallback)
    try:
        result = await chat_service.process_message(
            chat_id=chat_id,
            user_message=message_data.message,
            feature_id=feature_id,
            user_id=current_user.id,
            use_rag=message_data.use_rag,
            use_db=message_data.use_db,
            rag_top_k=message_data.rag_top_k,
            user_accesses=current_user.accesses,
            user_store_id=current_user.store_id,
        )

        # Convert sources to schema format
        sources = [
            MessageSource(
                document_id=source.get("document_id"),
                filename=source.get("filename"),
                file_type=source.get("file_type"),
                chunk_type=source.get("chunk_type"),
                chunk_index=source.get("chunk_index"),
                table_id=source.get("table_id"),
                row_start=source.get("row_start"),
                row_end=source.get("row_end"),
                section_path=source.get("section_path"),
                page=source.get("page"),
                page_label=source.get("page_label"),
            )
            for source in result.get("sources", [])
        ]

        # Build response
        response = SendMessageResponse(
            message=result["response"],
            user_message_id=result["user_message_id"],
            assistant_message_id=result["assistant_message_id"],
            sources=sources,
            persona_model=result["persona_model"],
            chat_id=chat_id,
            db_query_result=result.get("db_query_result"),
            attachments=result.get("attachments", []),
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}",
        )


@router.put(
    "/features/{feature_id}/chats/{chat_id}",
    response_model=ChatResponse,
    tags=["chats"],
)
def update_chat(
    feature_id: int,
    chat_id: int,
    chat_update: ChatUpdate,
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    Update a chat's title.

    - **feature_id**: ID of the feature
    - **chat_id**: ID of the chat
    - **title**: New title for the chat

    Returns the updated chat.
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Validate chat exists and belongs to user
    chat = memory_service.get_chat_by_id(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {chat_id} not found",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this chat",
        )

    if chat.feature_id != feature_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chat {chat_id} does not belong to feature {feature_id}",
        )

    # Update chat
    if chat_update.title:
        updated_chat = memory_service.update_chat(chat_id, chat_update.title)

        response = ChatResponse(
            id=updated_chat.id,
            user_id=updated_chat.user_id,
            feature_id=updated_chat.feature_id,
            title=updated_chat.title,
            created_at=updated_chat.created_at,
            updated_at=updated_chat.updated_at,
            message_count=len(updated_chat.messages) if updated_chat.messages else 0,
        )

        return response

    # If no update provided, return current chat
    response = ChatResponse(
        id=chat.id,
        user_id=chat.user_id,
        feature_id=chat.feature_id,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=len(chat.messages) if chat.messages else 0,
    )

    return response


@router.delete(
    "/features/{feature_id}/chats/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["chats"],
)
def delete_chat(
    feature_id: int,
    chat_id: int,
    current_user: User = Depends(get_current_user),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    Delete a chat and all its messages.

    - **feature_id**: ID of the feature
    - **chat_id**: ID of the chat to delete

    Returns 204 No Content on success.
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Validate chat exists and belongs to user
    chat = memory_service.get_chat_by_id(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {chat_id} not found",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this chat",
        )

    if chat.feature_id != feature_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chat {chat_id} does not belong to feature {feature_id}",
        )

    # Delete chat
    memory_service.delete_chat(chat_id)

    return None
