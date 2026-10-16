"""Code-owned policy for inbound support-email attachments."""

from typing import Final

MAX_ATTACHMENTS_PER_EMAIL: Final[int] = 10
MAX_FILE_SIZE_BYTES: Final[int] = 20 * 1024 * 1024
MAX_EMAIL_ATTACHMENTS_SIZE_BYTES: Final[int] = 25 * 1024 * 1024
MAX_CONVERSATION_ATTACHMENTS_SIZE_BYTES: Final[int] = 50 * 1024 * 1024
MAX_FILENAME_CHARACTERS: Final[int] = 255
MAX_ATTACHMENT_TOKENS_PER_AGENT_RUN: Final[int] = 32_000
OPENAI_FILE_INACTIVITY_DAYS: Final[int] = 21
UNUPLOADED_LOCAL_FILE_RETENTION_DAYS: Final[int] = 21

# The backend team's AI ticket upload route. Its authorization and multipart
# behavior still need verification against the configured ticket API.
TICKET_ATTACHMENT_UPLOAD_PATH: Final[str] = (
    "/store-panel/file/{owner_type}/{ticket_id}/ai"
)
TICKET_ATTACHMENT_OWNER_TYPE: Final[str] = "field-service-ticket"

AUDIO_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {"aac", "flac", "m4a", "mp3", "ogg", "wav", "webm"}
)
VIDEO_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {"avi", "mov", "mp4", "mpeg", "mpg", "webm"}
)
EMAIL_DOCUMENT_IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        "csv",
        "docx",
        "jpeg",
        "jpg",
        "md",
        "pdf",
        "png",
        "txt",
        "webp",
        "xlsx",
    }
)
ALLOWED_EMAIL_EXTENSIONS: Final[frozenset[str]] = (
    EMAIL_DOCUMENT_IMAGE_EXTENSIONS
    | AUDIO_EXTENSIONS
    | VIDEO_EXTENSIONS
)

# Give known executable types a specific error. The allowlist above also rejects
# unknown extensions and archives before an adapter fetches a separate file body.
DANGEROUS_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        "apk",
        "app",
        "bat",
        "cmd",
        "com",
        "cpl",
        "dll",
        "dmg",
        "exe",
        "hta",
        "iso",
        "jar",
        "js",
        "jse",
        "lnk",
        "msi",
        "msp",
        "ps1",
        "py",
        "reg",
        "scr",
        "sh",
        "vb",
        "vbe",
        "vbs",
        "wsf",
    }
)
