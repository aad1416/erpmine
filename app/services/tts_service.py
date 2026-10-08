from typing import Optional
from fastapi import HTTPException, status
from app.config.setting import settings


class TTSService:
    """
    Text-to-Speech Service
    
    Responsibilities:
    - Convert text to speech audio
    - Support multiple TTS providers (OpenAI TTS by default)
    - Return audio as bytes (MP3 format)
    """
    
    def __init__(self, provider: str = "openai", model: str = "tts-1"):
        """
        Initialize TTS Service
        
        Args:
            provider: TTS provider name (default: "openai")
            model: Model name to use (default: "tts-1" for OpenAI, or "tts-1-hd" for higher quality)
        """
        self.provider = provider.lower()
        self.model = model
        
        # Initialize provider client
        if self.provider == "openai":
            self._init_openai_client()
        else:
            raise ValueError(f"Unsupported TTS provider: {provider}")
    
    def _init_openai_client(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai is not installed. "
                "Please install it with: pip install openai"
            )
        
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found in settings")
        
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def _validate_text(self, text: str):
        """
        Validate input text
        
        Args:
            text: Text to validate
        
        Raises:
            HTTPException: If text is invalid
        """
        if not text or not text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text cannot be empty"
            )
        
        # OpenAI TTS has a limit of 4096 characters
        max_length = 4096
        if len(text) > max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Text length ({len(text)} characters) exceeds maximum allowed length ({max_length} characters)"
            )
    
    def _synthesize_with_openai(self, text: str, voice: str = "alloy") -> bytes:
        """
        Synthesize speech using OpenAI TTS API
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        
        Returns:
            Audio data as bytes (MP3 format)
        """
        try:
            # Call OpenAI TTS API
            response = self.client.audio.speech.create(
                model=self.model,
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            # Read audio content
            audio_bytes = response.content
            
            return audio_bytes
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error synthesizing speech with OpenAI: {str(e)}"
            )
    
    def synthesize(
        self, 
        text: str, 
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        Synthesize speech from text
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (provider-specific, default: "alloy" for OpenAI)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Audio data as bytes (MP3 format)
        
        Raises:
            HTTPException: If validation fails or synthesis error occurs
        """
        # Validate input text
        self._validate_text(text)
        
        # Synthesize based on provider
        if self.provider == "openai":
            default_voice = voice or "alloy"
            return self._synthesize_with_openai(text, voice=default_voice)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Provider {self.provider} not implemented"
            )
    
    async def synthesize_async(
        self, 
        text: str, 
        voice: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        Async version of synthesize method
        
        Note: Currently uses sync implementation.
        For true async, consider using asyncio.to_thread or a task queue.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (provider-specific, default: "alloy" for OpenAI)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Audio data as bytes (MP3 format)
        
        Raises:
            HTTPException: If validation fails or synthesis error occurs
        """
        # For now, we'll use the sync version
        # In production, you might want to use asyncio.to_thread() or a background task queue
        return self.synthesize(text, voice=voice, **kwargs)


# Create singleton instance with default provider (OpenAI TTS)
tts_service = TTSService(provider="openai", model="tts-1")
