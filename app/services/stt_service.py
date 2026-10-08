from typing import Optional, Union, BinaryIO
from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
import io
import tempfile
from app.config.setting import settings


class STTService:
    """
    Speech-to-Text Service

    Responsibilities:
    - Transcribe audio files to text
    - Validate audio file format, size, and duration
    - Support multiple STT providers (OpenAI Whisper by default)
    - Convert audio formats if needed
    """

    # Supported audio formats
    SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac"}
    SUPPORTED_MIME_TYPES = {
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
        "audio/ogg",
        "audio/vorbis",
        "audio/webm",
        "audio/flac",
        "audio/aac",
        "audio/x-aac",
    }

    def __init__(self, provider: str = "openai", model: str = "whisper-1"):
        """
        Initialize STT Service

        Args:
            provider: STT provider name (default: "openai")
            model: Model name to use (default: "whisper-1" for OpenAI)
        """
        self.provider = provider.lower()
        self.model = model
        self.max_size_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
        self.max_duration_seconds = settings.MAX_AUDIO_DURATION_SECONDS

        # Initialize provider client
        if self.provider == "openai":
            self._init_openai_client()
        else:
            raise ValueError(f"Unsupported STT provider: {provider}")

    def _init_openai_client(self):
        """Initialize OpenAI client"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai is not installed. " "Please install it with: pip install openai"
            )

        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found in settings")

        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def _validate_file_format(self, filename: str, mime_type: Optional[str] = None):
        """
        Validate audio file format

        Args:
            filename: Name of the file
            mime_type: MIME type of the file (optional)

        Raises:
            HTTPException: If format is not supported
        """
        file_ext = Path(filename).suffix.lower()

        if file_ext not in self.SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format: {file_ext}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS)}",
            )

        if mime_type and mime_type not in self.SUPPORTED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MIME type: {mime_type}",
            )

    def _validate_file_size(self, file_size: int):
        """
        Validate audio file size

        Args:
            file_size: Size of the file in bytes

        Raises:
            HTTPException: If file size exceeds limit
        """
        if file_size > self.max_size_bytes:
            max_mb = settings.MAX_AUDIO_SIZE_MB
            actual_mb = file_size / (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Audio file size ({actual_mb:.2f}MB) exceeds maximum allowed size ({max_mb}MB)",
            )

    def _get_audio_duration(self, audio_data: bytes, file_ext: str) -> float:
        """
        Get duration of audio file in seconds

        Args:
            audio_data: Audio file content as bytes
            file_ext: File extension (e.g., '.mp3', '.wav')

        Returns:
            Duration in seconds

        Raises:
            HTTPException: If audio file cannot be decoded
        """
        try:
            # Remove leading dot from extension
            format_name = file_ext.lstrip(".")

            # Handle special format names
            format_map = {"m4a": "mp4", "wave": "wav"}
            format_name = format_map.get(format_name, format_name)

            # Load audio using pydub
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format_name)
            duration_seconds = (
                len(audio) / 1000.0
            )  # pydub returns duration in milliseconds

            return duration_seconds

        except CouldntDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not decode audio file: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing audio file: {str(e)}",
            )

    def _validate_audio_duration(self, duration_seconds: float):
        """
        Validate audio duration

        Args:
            duration_seconds: Duration of audio in seconds

        Raises:
            HTTPException: If duration exceeds limit
        """
        if duration_seconds > self.max_duration_seconds:
            max_minutes = self.max_duration_seconds / 60
            actual_minutes = duration_seconds / 60
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio duration ({actual_minutes:.2f} minutes) exceeds maximum allowed duration ({max_minutes:.0f} minutes)",
            )

    def _transcribe_with_openai(self, audio_data: bytes, filename: str) -> str:
        """
        Transcribe audio using OpenAI Whisper API

        Args:
            audio_data: Audio file content as bytes
            filename: Original filename (used for format detection)

        Returns:
            Transcribed text
        """
        try:
            # Create a file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = filename  # OpenAI uses filename for format detection

            # Call OpenAI Whisper API
            transcript = self.client.audio.transcriptions.create(
                model=self.model, file=audio_file, response_format="text", language="en"
            )

            return transcript

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error transcribing audio with OpenAI: {str(e)}",
            )

    def transcribe(
        self, file: Union[UploadFile, bytes, BinaryIO], filename: Optional[str] = None
    ) -> str:
        """
        Transcribe audio file to text

        Args:
            file: Audio file as UploadFile, bytes, or file-like object
            filename: Filename (required if file is bytes or BinaryIO)

        Returns:
            Transcribed text as string

        Raises:
            HTTPException: If validation fails or transcription error occurs
        """
        # Handle different input types
        # Check if it's an UploadFile by checking for the 'file' attribute
        if hasattr(file, "filename") and hasattr(file, "file"):
            # It's an UploadFile
            filename = file.filename
            mime_type = file.content_type if hasattr(file, "content_type") else None

            # Ensure file pointer is at the beginning
            file.file.seek(0)
            audio_data = file.file.read()
            # Reset pointer after reading for potential re-use
            file.file.seek(0)
        elif isinstance(file, bytes):
            if not filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Filename is required when providing audio as bytes",
                )
            mime_type = None
            audio_data = file
        else:  # BinaryIO
            if not filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Filename is required when providing audio as file object",
                )
            mime_type = None
            # Ensure file pointer is at the beginning
            if hasattr(file, "seek"):
                file.seek(0)
            audio_data = file.read()

        # Validate file format
        self._validate_file_format(filename, mime_type)

        # Validate file size
        file_size = len(audio_data)
        self._validate_file_size(file_size)

        # Get and validate audio duration
        file_ext = Path(filename).suffix.lower()
        duration = self._get_audio_duration(audio_data, file_ext)
        self._validate_audio_duration(duration)

        # Transcribe based on provider
        if self.provider == "openai":
            return self._transcribe_with_openai(audio_data, filename)
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Provider {self.provider} not implemented",
            )

    async def transcribe_async(
        self, file: Union[UploadFile, bytes, BinaryIO], filename: Optional[str] = None
    ) -> str:
        """
        Async version of transcribe method

        Note: Currently uses sync implementation as pydub is sync.
        For true async, consider using asyncio.to_thread or a task queue.

        Args:
            file: Audio file as UploadFile, bytes, or file-like object
            filename: Filename (required if file is bytes or BinaryIO)

        Returns:
            Transcribed text as string

        Raises:
            HTTPException: If validation fails or transcription error occurs
        """
        # For now, we'll use the sync version
        # In production, you might want to use asyncio.to_thread() or a background task queue
        return self.transcribe(file, filename)


# Create singleton instance with default provider (OpenAI Whisper)
stt_service = STTService(provider="openai", model="whisper-1")
