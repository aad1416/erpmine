from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_admin_user
from app.dependencies.chat import get_admin_chat_agent_service, get_memory_service
from app.dependencies.features import get_feature_service
from app.db.models.Users import User
from app.services.admin_chat_agent_service import AdminChatAgentService
from app.services.memory_service import MemoryService
from app.services.feature_service import FeatureService
from app.schemas.chats import (
    AdminMessageRequest,
    AdminMessageResponse,
    IntentDetectionResult,
    PersonaUpdateResult,
    MessageSource,
)

router = APIRouter()


@router.post(
    "/admin/features/{feature_id}/chats/{chat_id}/admin-message",
    response_model=AdminMessageResponse,
    tags=["admin", "chats"],
)
async def send_admin_message(
    feature_id: int,
    chat_id: int,
    message_data: AdminMessageRequest,
    admin_user: User = Depends(get_admin_user),
    admin_chat_service: AdminChatAgentService = Depends(get_admin_chat_agent_service),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
):
    """
    Send an admin message processed by an OpenAI Agents SDK agent with tools
    (update_persona, retrieve_documents, query_database). Non-OpenAI persona
    models fall back to the legacy 3-step AdminChatService orchestration.

    This endpoint allows admins to:
    - Modify feature personas through natural language conversation
    - Query documents and ERP data while simultaneously updating persona
    - Get comprehensive metadata about all actions taken

    - **feature_id**: ID of the feature
    - **chat_id**: ID of the chat (can be any chat, admin has access to all)
    - **message**: Admin's message content

    Returns comprehensive response with:
    - Intent detection result (behavior_change, rag_data flags)
    - Persona update details (old prompt, new prompt) if updated
    - RAG sources if data was retrieved
    - Final synthesized response
    """
    # Validate feature exists
    feature = feature_service.get_feature_by_id(feature_id)
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature with id {feature_id} not found",
        )

    # Validate chat exists (admin can access any chat)
    chat = memory_service.get_chat_by_id(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat with id {chat_id} not found",
        )

    # Verify chat belongs to feature
    if chat.feature_id != feature_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chat {chat_id} does not belong to feature {feature_id}",
        )

    # Process admin message using AdminChatAgentService (agentic orchestration)
    try:
        result = await admin_chat_service.process_admin_message(
            chat_id=chat_id,
            user_message=message_data.message,
            feature_id=feature_id,
            admin_user_id=admin_user.id,
            user_accesses=admin_user.accesses,
            user_store_id=admin_user.store_id,
        )

        # Build response with full metadata
        intent_result = IntentDetectionResult(
            behavior_change=result["intent"]["behavior_change"],
            rag_data=result["intent"]["rag_data"],
        )

        persona_update_result = None
        if result.get("persona_update"):
            persona_update_result = PersonaUpdateResult(
                updated=result["persona_update"]["updated"],
                old_prompt=result["persona_update"]["old_prompt"],
                new_prompt=result["persona_update"]["new_prompt"],
            )

        # Convert sources to schema format
        sources = [
            MessageSource(
                document_id=source.get("document_id"),
                page=source.get("page", -1),
            )
            for source in result.get("sources", [])
        ]

        response = AdminMessageResponse(
            response=result["response"],
            intent=intent_result,
            persona_update=persona_update_result,
            sources=sources,
            user_message_id=result["user_message_id"],
            assistant_message_id=result["assistant_message_id"],
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
            detail=f"Failed to process admin message: {str(e)}",
        )
