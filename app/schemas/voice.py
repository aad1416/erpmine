from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
from app.schemas.chats import MessageSource, IntentDetectionResult, PersonaUpdateResult


class VoiceMessageResponse(BaseModel):
    """Response schema for voice message endpoint"""
    
    transcribed_text: str = Field(..., description="Transcribed text from audio input")
    response_text: str = Field(..., description="Assistant's text response")
    audio_response: Optional[str] = Field(
        None, 
        description="Base64 encoded audio response (MP3 format) if speech_output=true"
    )
    user_message_id: int = Field(..., description="ID of saved user message")
    assistant_message_id: int = Field(..., description="ID of saved assistant message")
    sources: List[MessageSource] = Field(
        default_factory=list, description="Sources used for response"
    )
    persona_model: str = Field(..., description="LLM model used for generation")
    chat_id: int = Field(..., description="Chat ID")


class AdminVoiceMessageResponse(VoiceMessageResponse):
    """
    Response schema for admin voice message endpoint.

    Extends VoiceMessageResponse with admin-specific metadata returned by the
    multi-agent admin chat orchestration (intent detection + optional persona update).
    """

    intent: IntentDetectionResult = Field(
        ..., description="Detected user intent (behavior_change, rag_data)"
    )
    persona_update: Optional[PersonaUpdateResult] = Field(
        None,
        description="Persona update details (only present if behavior_change occurred)",
    )
    db_query_result: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "DB tool audit (OpenAI Agents path). Legacy AdminChatService "
            "path does not populate this field."
        ),
    )


class VoiceMessageRequest(BaseModel):
    """Request schema for voice message (used for form fields)"""
    
    speech_output: bool = Field(
        default=False, 
        description="Whether to return audio response in addition to text"
    )
    use_rag: bool = Field(
        default=True, 
        description="Whether document retrieval tool / RAG is enabled"
    )
    use_db: bool = Field(
        default=False,
        description="Whether the database query tool may run (OpenAI Agents path)",
    )
    rag_top_k: int = Field(
        default=5, 
        ge=1, 
        le=20, 
        description="Number of documents to retrieve"
    )
    voice: Optional[str] = Field(
        default=None,
        description="Voice to use for TTS (alloy, echo, fable, onyx, nova, shimmer). Defaults to 'alloy'"
    )


class STTResponse(BaseModel):
    """Response schema for standalone speech-to-text endpoint"""

    transcribed_text: str = Field(..., description="Transcribed text from audio input")


class TTSRequest(BaseModel):
    """Request schema for standalone text-to-speech endpoint"""

    text: str = Field(..., description="Text to synthesize into speech")
    voice: Optional[str] = Field(
        default=None,
        description="Voice to use for TTS (alloy, echo, fable, onyx, nova, shimmer). Defaults to 'alloy'",
    )


class TTSResponse(BaseModel):
    """Response schema for standalone text-to-speech endpoint"""

    audio_response: str = Field(..., description="Base64 encoded audio response (MP3 format)")
