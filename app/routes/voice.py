import base64
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Optional

from app.dependencies.auth import get_current_user, get_admin_user
from app.dependencies.chat import (
    get_chat_agent_service,
    get_memory_service,
    get_admin_chat_agent_service,
    get_persona_service,
)
from app.dependencies.features import get_feature_service
from app.dependencies.voice import get_stt_service, get_tts_service
from app.db.models.Users import User
from app.services.chat_agent_service import ChatAgentService
from app.services.admin_chat_agent_service import AdminChatAgentService
from app.services.memory_service import MemoryService
from app.services.feature_service import FeatureService
from app.services.persona_service import PersonaService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService
from app.schemas.voice import (
    VoiceMessageResponse,
    AdminVoiceMessageResponse,
    STTResponse,
    TTSRequest,
    TTSResponse,
)
from app.schemas.chats import MessageSource, IntentDetectionResult, PersonaUpdateResult

router = APIRouter()


@router.post(
    "/voice/stt",
    response_model=STTResponse,
    tags=["voice"],
)
async def transcribe_audio(
    audio_file: UploadFile = File(
        ..., description="Audio file (WAV, MP3, M4A, OGG, WEBM, FLAC, AAC)"
    ),
    _: User = Depends(get_current_user),
    stt_service: STTService = Depends(get_stt_service),
):
    """
    Convert an audio file to text for any authenticated user.
    """
    try:
        transcribed_text = stt_service.transcribe(audio_file)
        if not transcribed_text or not transcribed_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not transcribe audio or audio is empty",
            )

        return STTResponse(transcribed_text=transcribed_text)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process speech-to-text request: {str(e)}",
        )


@router.post(
    "/voice/tts",
    response_model=TTSResponse,
    tags=["voice"],
)
async def synthesize_speech(
    request: TTSRequest,
    _: User = Depends(get_current_user),
    tts_service: TTSService = Depends(get_tts_service),
):
    """
    Convert text to speech for any authenticated user.
    """
    try:
        audio_bytes = tts_service.synthesize(text=request.text, voice=request.voice)
        audio_response_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        return TTSResponse(audio_response=audio_response_base64)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process text-to-speech request: {str(e)}",
        )


@router.post(
    "/features/{feature_id}/chats/{chat_id}/voice-message",
    response_model=VoiceMessageResponse,
    tags=["voice"],
)
async def send_voice_message(
    feature_id: int,
    chat_id: int,
    audio_file: UploadFile = File(
        ..., description="Audio file (WAV, MP3, M4A, OGG, WEBM, FLAC, AAC)"
    ),
    speech_output: bool = Form(False, description="Whether to return audio response"),
    use_rag: bool = Form(True, description="Whether document retrieval / RAG is enabled"),
    use_db: bool = Form(
        False, description="Whether the database query tool may run (OpenAI Agents path)"
    ),
    rag_top_k: int = Form(
        5, ge=1, le=20, description="Number of documents to retrieve"
    ),
    voice: Optional[str] = Form(
        None, description="Voice for TTS (alloy, echo, fable, onyx, nova, shimmer)"
    ),
    current_user: User = Depends(get_current_user),
    chat_service: ChatAgentService = Depends(get_chat_agent_service),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
    stt_service: STTService = Depends(get_stt_service),
    tts_service: TTSService = Depends(get_tts_service),
):
    """
    Send a voice message to a chat.

    Voice Chat Flow:
    1. Receive audio file from client
    2. Convert speech to text using STT Service (OpenAI Whisper)
    3. Delegate to ChatAgentService for processing (same as text chat)
    4. If speech_output=true, convert response to audio using TTS Service
    5. Return transcribed text, response text, and optional audio

    Audio Validation:
    - **Format**: WAV, MP3, M4A, OGG, WEBM, FLAC, AAC
    - **Size**: Max 5MB (configurable via MAX_AUDIO_SIZE_MB)
    - **Duration**: Max 2 minutes (configurable via MAX_AUDIO_DURATION_SECONDS)

    Args:
        - **feature_id**: ID of the feature
        - **chat_id**: ID of the chat
        - **audio_file**: Audio file with user's speech
        - **speech_output**: Whether to return audio response (default: False)
        - **use_rag**: Whether document retrieval / RAG is enabled (default: True)
        - **use_db**: Whether the DB query tool may run (default: False)
        - **rag_top_k**: Number of documents to retrieve (default: 5, max: 20)
        - **voice**: Voice to use for TTS (default: alloy)

    Returns:
        VoiceMessageResponse with transcribed text, response text, optional audio, and metadata
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

    try:
        # Step 1: Speech-to-Text
        # Convert audio to text using STT service
        # This validates format, size, and duration automatically
        transcribed_text = stt_service.transcribe(audio_file)

        if not transcribed_text or not transcribed_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not transcribe audio or audio is empty",
            )

        # Step 2: Process with ChatAgentService (same as text chat)
        result = await chat_service.process_message(
            chat_id=chat_id,
            user_message=transcribed_text,
            feature_id=feature_id,
            user_id=current_user.id,
            use_rag=use_rag,
            use_db=use_db,
            rag_top_k=rag_top_k,
        )

        response_text = result["response"]

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

        # Step 3: Text-to-Speech (Optional)
        audio_response_base64 = None
        if speech_output:
            # Convert response text to audio using TTS service
            audio_bytes = tts_service.synthesize(
                text=response_text, voice=voice  # Uses default "alloy" if voice is None
            )

            # Encode audio as base64 for JSON response
            audio_response_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Step 4: Build and return response
        response = VoiceMessageResponse(
            transcribed_text=transcribed_text,
            response_text=response_text,
            audio_response=audio_response_base64,
            user_message_id=result["user_message_id"],
            assistant_message_id=result["assistant_message_id"],
            sources=sources,
            persona_model=result["persona_model"],
            chat_id=chat_id,
            db_query_result=result.get("db_query_result"),
        )

        return response

    except HTTPException:
        # Re-raise HTTPExceptions (validation errors, etc.)
        raise
    except Exception as e:
        # Catch any other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process voice message: {str(e)}",
        )


@router.post(
    "/admin/features/{feature_id}/chats/{chat_id}/voice-message",
    response_model=AdminVoiceMessageResponse,
    tags=["admin", "voice"],
)
async def send_admin_voice_message(
    feature_id: int,
    chat_id: int,
    audio_file: UploadFile = File(
        ..., description="Audio file (WAV, MP3, M4A, OGG, WEBM, FLAC, AAC)"
    ),
    speech_output: bool = Form(False, description="Whether to return audio response"),
    voice: Optional[str] = Form(
        None, description="Voice for TTS (alloy, echo, fable, onyx, nova, shimmer)"
    ),
    admin_user: User = Depends(get_admin_user),
    admin_chat_service: AdminChatAgentService = Depends(get_admin_chat_agent_service),
    memory_service: MemoryService = Depends(get_memory_service),
    feature_service: FeatureService = Depends(get_feature_service),
    persona_service: PersonaService = Depends(get_persona_service),
    stt_service: STTService = Depends(get_stt_service),
    tts_service: TTSService = Depends(get_tts_service),
):
    """
    Send an admin voice message with multi-agent orchestration.

    Admin-only endpoint. Voice wrapper around the admin chat flow:
    1. Receive audio file from admin client
    2. Convert speech to text using STT Service (OpenAI Whisper)
    3. Delegate to AdminChatAgentService (OpenAI Agents SDK) with tools:
       - update_persona (persona changes)
       - retrieve_documents (RAG retrieval)
       - query_database (ERP data)
       Non-OpenAI persona models fall back to the legacy 3-step orchestration.
    4. If speech_output=true, convert synthesized response to audio using TTS
    5. Return transcribed text, response text, optional audio, and full admin metadata

    Audio Validation:
    - **Format**: WAV, MP3, M4A, OGG, WEBM, FLAC, AAC
    - **Size**: Max 5MB (configurable via MAX_AUDIO_SIZE_MB)
    - **Duration**: Max 2 minutes (configurable via MAX_AUDIO_DURATION_SECONDS)

    Args:
        - **feature_id**: ID of the feature
        - **chat_id**: ID of the chat (admin has access to all chats)
        - **audio_file**: Audio file with admin's speech
        - **speech_output**: Whether to return audio response (default: False)
        - **voice**: Voice to use for TTS (default: alloy)

    Returns:
        AdminVoiceMessageResponse with transcribed text, response text, optional audio,
        intent detection result, persona update details (if any), RAG sources, and metadata.
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

    try:
        # Step 1: Speech-to-Text
        # Convert audio to text using STT service
        # This validates format, size, and duration automatically
        transcribed_text = stt_service.transcribe(audio_file)

        if not transcribed_text or not transcribed_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not transcribe audio or audio is empty",
            )

        # Step 2: Process with AdminChatAgentService (agentic orchestration)
        result = await admin_chat_service.process_admin_message(
            chat_id=chat_id,
            user_message=transcribed_text,
            feature_id=feature_id,
            admin_user_id=admin_user.id,
            user_accesses=admin_user.accesses,
            user_store_id=admin_user.store_id,
        )

        response_text = result["response"]

        # Build intent / persona_update / sources from admin result
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

        sources = [
            MessageSource(
                document_id=source.get("document_id"),
                page=str(source.get("page", -1)),
            )
            for source in result.get("sources", [])
        ]

        # Step 3: Text-to-Speech (Optional)
        audio_response_base64 = None
        if speech_output:
            # Convert synthesized response text to audio using TTS service
            audio_bytes = tts_service.synthesize(
                text=response_text, voice=voice  # Uses default "alloy" if voice is None
            )
            audio_response_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Resolve persona_model for response metadata.
        # AdminChatService does not return persona_model directly, so fetch the
        # feature's configured persona model here.
        current_persona = persona_service.get_persona_for_feature(feature_id)
        persona_model = current_persona.model_name if current_persona else ""

        # Step 4: Build and return response
        response = AdminVoiceMessageResponse(
            transcribed_text=transcribed_text,
            response_text=response_text,
            audio_response=audio_response_base64,
            user_message_id=result["user_message_id"],
            assistant_message_id=result["assistant_message_id"],
            sources=sources,
            persona_model=persona_model,
            chat_id=chat_id,
            intent=intent_result,
            persona_update=persona_update_result,
            db_query_result=result.get("db_query_result"),
        )

        return response

    except HTTPException:
        # Re-raise HTTPExceptions (validation errors, etc.)
        raise
    except Exception as e:
        # Catch any other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process admin voice message: {str(e)}",
        )
