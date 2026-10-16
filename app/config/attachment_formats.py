"""Shared safe-format and parser limits for customer-supplied files.

Channel policies choose which of these formats they accept. Keeping this module
limited to format facts prevents a chat-policy change from silently changing the
email attachment contract.
"""

from typing import Final


DOCUMENT_IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset(
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
        "xls",
        "xlsx",
    }
)

MAX_EXTRACTED_TOKENS_PER_FILE: Final[int] = 16_000
MAX_SCANNED_PDF_PAGES: Final[int] = 15
MAX_TEXT_PDF_PAGES: Final[int] = 500

# Parser safety limits for compressed Office documents and decoded images.
MAX_OFFICE_UNCOMPRESSED_BYTES: Final[int] = 100 * 1024 * 1024
MAX_OFFICE_ARCHIVE_MEMBERS: Final[int] = 10_000
MAX_IMAGE_PIXELS: Final[int] = 40_000_000
MAX_FILENAME_CHARACTERS: Final[int] = 255
