from app.services.stt_service import STTService, stt_service
from app.services.tts_service import TTSService, tts_service


def get_stt_service() -> STTService:
    """
    Dependency injection for STT Service
    
    Returns the singleton STT service instance (OpenAI Whisper by default)
    """
    return stt_service


def get_tts_service() -> TTSService:
    """
    Dependency injection for TTS Service
    
    Returns the singleton TTS service instance (OpenAI TTS by default)
    """
    return tts_service
