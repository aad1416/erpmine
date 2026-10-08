# Voice Services Usage Guide

This document provides usage examples for the Speech-to-Text (STT) and Text-to-Speech (TTS) services.

## Speech-to-Text (STT) Service

### Basic Usage

```python
from app.services import stt_service
from fastapi import UploadFile

# Using default singleton (OpenAI Whisper)
async def transcribe_audio(audio_file: UploadFile):
    try:
        text = stt_service.transcribe(audio_file)
        return {"transcription": text}
    except HTTPException as e:
        # Handle validation errors (file size, duration, format)
        return {"error": e.detail}
```

### Custom Instance

```python
from app.services.stt_service import STTService

# Create custom instance with specific provider/model
custom_stt = STTService(provider="openai", model="whisper-1")
text = custom_stt.transcribe(audio_file)
```

### Validation

The STT service validates:
- **Format**: WAV, MP3, M4A, OGG, WEBM, FLAC, AAC
- **Size**: Max 5MB (configurable via `MAX_AUDIO_SIZE_MB`)
- **Duration**: Max 2 minutes (configurable via `MAX_AUDIO_DURATION_SECONDS`)

### Error Handling

```python
from fastapi import HTTPException, status

try:
    text = stt_service.transcribe(audio_file)
except HTTPException as e:
    if e.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
        # File too large
        print(f"File too large: {e.detail}")
    elif e.status_code == status.HTTP_400_BAD_REQUEST:
        # Invalid format or duration exceeded
        print(f"Validation error: {e.detail}")
```

## Text-to-Speech (TTS) Service

### Basic Usage

```python
from app.services import tts_service

# Convert text to speech (returns MP3 audio as bytes)
text = "Hello, this is a test of the text-to-speech service."
audio_bytes = tts_service.synthesize(text)

# Save to file
with open("output.mp3", "wb") as f:
    f.write(audio_bytes)

# Or return as FastAPI response
from fastapi.responses import Response

return Response(content=audio_bytes, media_type="audio/mpeg")
```

### Custom Instance with Voice Selection

```python
from app.services.tts_service import TTSService

# Create custom instance
custom_tts = TTSService(provider="openai", model="tts-1-hd")  # Higher quality

# Synthesize with specific voice
audio_bytes = custom_tts.synthesize(
    text="Hello world",
    voice="nova"  # Options: alloy, echo, fable, onyx, nova, shimmer
)
```

### Validation

The TTS service validates:
- **Text length**: Max 4096 characters (OpenAI limit)
- **Empty text**: Returns HTTP 400 if text is empty or only whitespace

### Error Handling

```python
from fastapi import HTTPException, status

try:
    audio_bytes = tts_service.synthesize(text)
except HTTPException as e:
    if e.status_code == status.HTTP_400_BAD_REQUEST:
        # Text too long or empty
        print(f"Validation error: {e.detail}")
    elif e.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        # API error
        print(f"Synthesis error: {e.detail}")
```

## Voice Chat API

The Voice Chat API is fully implemented and ready to use!

### Endpoint

```
POST /features/{feature_id}/chats/{chat_id}/voice-message
```

### Request Parameters

**Form Data:**
- `audio_file` (file, required): Audio file (WAV, MP3, M4A, OGG, WEBM, FLAC, AAC)
- `speech_output` (boolean, optional): Whether to return audio response (default: `false`)
- `use_rag` (boolean, optional): Whether to use RAG for context retrieval (default: `true`)
- `rag_top_k` (integer, optional): Number of documents to retrieve (default: `5`, max: `20`)
- `voice` (string, optional): Voice for TTS response (default: `alloy`)

### Response

```json
{
  "transcribed_text": "What is machine learning?",
  "response_text": "Machine learning is a subset of artificial intelligence...",
  "audio_response": "base64_encoded_mp3_audio_or_null",
  "user_message_id": 123,
  "assistant_message_id": 124,
  "sources": [
    {
      "document_id": "doc-123",
      "page": "5"
    }
  ],
  "persona_model": "gpt-4",
  "chat_id": 10
}
```

### Usage Examples

#### Example 1: Voice Input, Text Output (Default)

```bash
curl -X POST \
  "http://localhost:8000/features/1/chats/10/voice-message" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "audio_file=@recording.mp3" \
  -F "speech_output=false"
```

#### Example 2: Voice Input, Voice Output

```bash
curl -X POST \
  "http://localhost:8000/features/1/chats/10/voice-message" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "audio_file=@recording.mp3" \
  -F "speech_output=true" \
  -F "voice=nova"
```

#### Example 3: Python Client

```python
import requests
import base64

# Prepare request
url = "http://localhost:8000/features/1/chats/10/voice-message"
headers = {"Authorization": "Bearer YOUR_TOKEN"}
files = {"audio_file": open("recording.mp3", "rb")}
data = {
    "speech_output": True,
    "use_rag": True,
    "rag_top_k": 5,
    "voice": "alloy"
}

# Send request
response = requests.post(url, headers=headers, files=files, data=data)
result = response.json()

# Process response
print(f"Transcribed: {result['transcribed_text']}")
print(f"Response: {result['response_text']}")

# Save audio response if available
if result["audio_response"]:
    audio_bytes = base64.b64decode(result["audio_response"])
    with open("response.mp3", "wb") as f:
        f.write(audio_bytes)
```

#### Example 4: JavaScript/TypeScript Client

```typescript
const formData = new FormData();
formData.append('audio_file', audioBlob, 'recording.mp3');
formData.append('speech_output', 'true');
formData.append('voice', 'nova');

const response = await fetch(
  '/features/1/chats/10/voice-message',
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  }
);

const result = await response.json();

// Play audio response
if (result.audio_response) {
  const audioBlob = base64ToBlob(result.audio_response, 'audio/mpeg');
  const audioUrl = URL.createObjectURL(audioBlob);
  const audio = new Audio(audioUrl);
  audio.play();
}
```

### Voice Chat Flow

The endpoint implements the complete voice chat flow:

1. **Speech-to-Text (STT)**:
   - Validates audio format, size (5MB max), duration (2 min max)
   - Transcribes audio using OpenAI Whisper
   - Returns error if transcription fails

2. **Process with ChatService**:
   - Uses transcribed text as user message
   - Retrieves chat history
   - Gets feature persona
   - Performs RAG retrieval (if enabled)
   - Generates response using LLM

3. **Text-to-Speech (TTS)** (Optional):
   - If `speech_output=true`, converts response to audio
   - Uses OpenAI TTS with selected voice
   - Returns audio as base64-encoded MP3

4. **Response**:
   - Returns transcribed text, response text, optional audio
   - Includes message IDs, sources, and metadata

## Environment Configuration

Add these to your `.env` file:

```bash
# STT Configuration
MAX_AUDIO_SIZE_MB=5
MAX_AUDIO_DURATION_SECONDS=120

# Required API Keys
OPENAI_API_KEY=your-openai-api-key-here
```

## Available OpenAI TTS Voices

- **alloy** (default): Balanced, neutral voice
- **echo**: Clear, professional voice
- **fable**: Warm, expressive voice
- **onyx**: Deep, authoritative voice
- **nova**: Energetic, engaging voice
- **shimmer**: Soft, pleasant voice

## Model Options

### STT (Speech-to-Text)
- `whisper-1`: OpenAI's Whisper model (default)

### TTS (Text-to-Speech)
- `tts-1`: Standard quality, faster, more affordable (default)
- `tts-1-hd`: Higher quality, slower, more expensive

## Async Support

Both services include async methods:

```python
# Async STT
text = await stt_service.transcribe_async(audio_file)

# Async TTS
audio_bytes = await tts_service.synthesize_async(text)
```

**Note**: Current async implementations wrap sync operations. For production with high load, consider using `asyncio.to_thread()` or a background task queue like Celery.
