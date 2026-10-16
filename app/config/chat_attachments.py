"""Code-level policy for feature-chat attachments.

These values intentionally are not environment settings. They define the product
contract for chat attachments and should change through a reviewed code change.
"""

from typing import Final

from app.config.attachment_formats import (
    DOCUMENT_IMAGE_EXTENSIONS,
)


MAX_ATTACHMENTS_PER_MESSAGE: Final[int] = 10
MAX_FILE_SIZE_BYTES: Final[int] = 20 * 1024 * 1024
MAX_UPLOAD_BATCH_SIZE_BYTES: Final[int] = 100 * 1024 * 1024
MAX_DIRECT_VISUAL_INPUT_SIZE_BYTES: Final[int] = 50 * 1024 * 1024

MAX_EXTRACTED_TOKENS_PER_REQUEST: Final[int] = 32_000
CHAT_HISTORY_TOKEN_BUDGET: Final[int] = 24_000

OPENAI_FILE_RETENTION_DAYS: Final[int] = 21

# Chat accepts every supported document/image format. Email has its own explicit policy.
CHAT_ALLOWED_EXTENSIONS: Final[frozenset[str]] = DOCUMENT_IMAGE_EXTENSIONS
