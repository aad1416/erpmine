"""Validation, classification, and local extraction for feature-chat attachments."""

from __future__ import annotations

import re
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image, UnidentifiedImageError

from app.config.attachment_formats import (
    MAX_EXTRACTED_TOKENS_PER_FILE,
    MAX_IMAGE_PIXELS,
    MAX_OFFICE_ARCHIVE_MEMBERS,
    MAX_OFFICE_UNCOMPRESSED_BYTES,
    MAX_SCANNED_PDF_PAGES,
    MAX_TEXT_PDF_PAGES,
)
from app.config.chat_attachments import CHAT_ALLOWED_EXTENSIONS
from app.utils.fast_document_parser import FastDocumentParser
from app.utils.token_count import count_tokens


class AttachmentValidationError(ValueError):
    """The uploaded file is invalid or unsupported."""


class AttachmentLimitError(AttachmentValidationError):
    """The file is valid but exceeds the chat-attachment product limits."""


@dataclass(frozen=True)
class ProcessedAttachment:
    extension: str
    mime_type: str
    kind: str
    extracted_text: str | None = None
    token_count: int = 0
    page_count: int | None = None
    image_count: int | None = None


@dataclass(frozen=True)
class _PdfAnalysis:
    page_count: int
    image_count: int
    scanned_pages: int
    significant_visual_pages: int
    meaningful_characters: int
    native_token_count: int

    @property
    def is_scanned(self) -> bool:
        if self.page_count == 0:
            return False
        return (
            self.scanned_pages / self.page_count >= 0.6
            or self.meaningful_characters < 100
        )

    @property
    def is_visual(self) -> bool:
        return self.significant_visual_pages > 0


class ChatAttachmentProcessor:
    """Processes only formats approved for chatbot attachments.

    It deliberately constructs ``FastDocumentParser`` without a LlamaParse fallback.
    Images and scanned PDFs are classified for OpenAI vision instead of OCR/parsing.
    """

    _IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})
    _TEXT_EXTENSIONS = frozenset({"txt", "md", "csv"})
    _OFFICE_EXTENSIONS = frozenset({"docx", "xlsx"})
    _MIME_TYPES = {
        "csv": "text/csv",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "md": "text/markdown",
        "pdf": "application/pdf",
        "png": "image/png",
        "txt": "text/plain",
        "webp": "image/webp",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def __init__(self) -> None:
        self._parser = FastDocumentParser(llama_fallback_parser=None)

    def process(self, file_path: str | Path, original_filename: str) -> ProcessedAttachment:
        path = Path(file_path)
        extension = Path(original_filename).suffix.lower().lstrip(".")
        if extension not in CHAT_ALLOWED_EXTENSIONS:
            allowed = ", ".join(f".{item}" for item in sorted(CHAT_ALLOWED_EXTENSIONS))
            raise AttachmentValidationError(
                f"Unsupported attachment type '.{extension or '(none)'}'. Allowed: {allowed}"
            )

        if extension in self._IMAGE_EXTENSIONS:
            return self._process_image(path, extension)
        if extension == "pdf":
            return self._process_pdf(path, extension)
        if extension in self._OFFICE_EXTENSIONS:
            self._validate_office_archive(path, extension)
        elif extension == "xls":
            self._validate_legacy_excel(path)
        elif extension in self._TEXT_EXTENSIONS:
            self._validate_text_file(path)

        return self._process_text_document(path, extension)

    def count_tokens(self, text: str) -> int:
        return count_tokens(text)

    def _process_image(self, path: Path, extension: str) -> ProcessedAttachment:
        expected_format = "JPEG" if extension in {"jpg", "jpeg"} else extension.upper()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    actual_format = (image.format or "").upper()
                    width, height = image.size
                    if actual_format != expected_format:
                        raise AttachmentValidationError(
                            f"File extension '.{extension}' does not match its image content."
                        )
                    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                        raise AttachmentLimitError(
                            f"Image dimensions exceed the {MAX_IMAGE_PIXELS:,}-pixel limit."
                        )
                    if getattr(image, "is_animated", False):
                        raise AttachmentValidationError("Animated images are not supported.")
                    image.verify()
        except AttachmentValidationError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise AttachmentLimitError("The decoded image is too large to process safely.") from exc
        except (UnidentifiedImageError, OSError) as exc:
            raise AttachmentValidationError("The image is corrupted or invalid.") from exc

        return ProcessedAttachment(
            extension=extension,
            mime_type=self._MIME_TYPES[extension],
            kind="image",
            image_count=1,
        )

    def _process_pdf(self, path: Path, extension: str) -> ProcessedAttachment:
        with path.open("rb") as file_handle:
            header = file_handle.read(1024)
        if b"%PDF-" not in header:
            raise AttachmentValidationError("File extension '.pdf' does not match its content.")

        analysis = self._analyze_pdf(path)
        if analysis.is_scanned:
            if analysis.page_count > MAX_SCANNED_PDF_PAGES:
                raise AttachmentLimitError(
                    "Scanned or image-only PDFs are limited to "
                    f"{MAX_SCANNED_PDF_PAGES} pages."
                )
            return ProcessedAttachment(
                extension=extension,
                mime_type=self._MIME_TYPES[extension],
                kind="pdf_scanned",
                page_count=analysis.page_count,
                image_count=analysis.image_count,
            )

        if analysis.native_token_count > MAX_EXTRACTED_TOKENS_PER_FILE:
            raise AttachmentLimitError(
                f"Extracted content contains at least {analysis.native_token_count:,} tokens; "
                f"the per-file limit is {MAX_EXTRACTED_TOKENS_PER_FILE:,}."
            )

        try:
            parsed = self._parser.parse_file(str(path), extension)
        except Exception as exc:
            raise AttachmentValidationError(
                "The PDF is corrupted or could not be parsed."
            ) from exc
        kind = "pdf_mixed" if analysis.is_visual else "document"
        return self._checked_text_result(
            extension=extension,
            text=parsed,
            kind=kind,
            page_count=analysis.page_count,
            image_count=analysis.image_count,
        )

    def _analyze_pdf(self, path: Path) -> _PdfAnalysis:
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise AttachmentValidationError("The PDF is corrupted or invalid.") from exc

        try:
            if document.needs_pass:
                raise AttachmentValidationError("Password-protected PDFs are not supported.")
            if document.page_count < 1:
                raise AttachmentValidationError("The PDF has no pages.")
            if document.page_count > MAX_TEXT_PDF_PAGES:
                raise AttachmentLimitError(
                    f"PDFs are limited to {MAX_TEXT_PDF_PAGES} pages."
                )

            image_count = 0
            scanned_pages = 0
            significant_visual_pages = 0
            meaningful_characters = 0
            native_token_count = 0

            for page in document:
                raw_page_text = page.get_text("text")
                page_text = re.sub(r"\s+", "", raw_page_text)
                char_count = len(page_text)
                meaningful_characters += char_count
                native_token_count += self.count_tokens(raw_page_text)
                page_area = max(float(page.rect.get_area()), 1.0)
                page_images = page.get_images(full=True)
                image_count += len(page_images)
                largest_image_coverage = 0.0

                for image in page_images:
                    try:
                        for rect in page.get_image_rects(image[0]):
                            largest_image_coverage = max(
                                largest_image_coverage,
                                min(1.0, float(rect.get_area()) / page_area),
                            )
                    except Exception:
                        # A malformed image reference should not make otherwise readable
                        # text inaccessible.
                        continue

                if largest_image_coverage >= 0.2:
                    significant_visual_pages += 1
                if char_count < 50 and largest_image_coverage >= 0.7:
                    scanned_pages += 1

            return _PdfAnalysis(
                page_count=document.page_count,
                image_count=image_count,
                scanned_pages=scanned_pages,
                significant_visual_pages=significant_visual_pages,
                meaningful_characters=meaningful_characters,
                native_token_count=native_token_count,
            )
        except AttachmentValidationError:
            raise
        except Exception as exc:
            raise AttachmentValidationError("The PDF is corrupted or invalid.") from exc
        finally:
            document.close()

    def _process_text_document(self, path: Path, extension: str) -> ProcessedAttachment:
        try:
            parsed = self._parser.parse_file(str(path), extension)
        except AttachmentValidationError:
            raise
        except Exception as exc:
            raise AttachmentValidationError(
                f"The {extension.upper()} file is corrupted or could not be parsed."
            ) from exc
        return self._checked_text_result(extension=extension, text=parsed)

    def _checked_text_result(
        self,
        *,
        extension: str,
        text: str,
        kind: str = "document",
        page_count: int | None = None,
        image_count: int | None = None,
    ) -> ProcessedAttachment:
        text = text.strip()
        if not text:
            raise AttachmentValidationError("No usable text could be extracted from the file.")
        token_count = self.count_tokens(text)
        if token_count > MAX_EXTRACTED_TOKENS_PER_FILE:
            raise AttachmentLimitError(
                f"Extracted content contains {token_count:,} tokens; the per-file limit "
                f"is {MAX_EXTRACTED_TOKENS_PER_FILE:,}."
            )
        return ProcessedAttachment(
            extension=extension,
            mime_type=self._MIME_TYPES[extension],
            kind=kind,
            extracted_text=text,
            token_count=token_count,
            page_count=page_count,
            image_count=image_count,
        )

    def _validate_office_archive(self, path: Path, extension: str) -> None:
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if len(members) > MAX_OFFICE_ARCHIVE_MEMBERS:
                    raise AttachmentLimitError("The Office document contains too many parts.")
                uncompressed_size = sum(member.file_size for member in members)
                if uncompressed_size > MAX_OFFICE_UNCOMPRESSED_BYTES:
                    raise AttachmentLimitError(
                        "The expanded Office document exceeds the processing limit."
                    )
                if any(member.flag_bits & 0x1 for member in members):
                    raise AttachmentValidationError(
                        "Password-protected Office documents are not supported."
                    )
                names = {member.filename for member in members}
                expected_prefix = "word/" if extension == "docx" else "xl/"
                if "[Content_Types].xml" not in names or not any(
                    name.startswith(expected_prefix) for name in names
                ):
                    raise AttachmentValidationError(
                        f"File extension '.{extension}' does not match its content."
                    )
        except AttachmentValidationError:
            raise
        except (OSError, zipfile.BadZipFile) as exc:
            raise AttachmentValidationError(
                f"The {extension.upper()} file is corrupted or invalid."
            ) from exc

    @staticmethod
    def _validate_legacy_excel(path: Path) -> None:
        with path.open("rb") as file_handle:
            header = file_handle.read(8)
        if not header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise AttachmentValidationError("File extension '.xls' does not match its content.")

    @staticmethod
    def _validate_text_file(path: Path) -> None:
        with path.open("rb") as file_handle:
            prefix = file_handle.read(8192)
        if b"\x00" in prefix:
            raise AttachmentValidationError("The text file contains binary data.")
        decoded = prefix.decode("utf-8", errors="replace")
        controls = sum(
            1
            for character in decoded
            if ord(character) < 32 and character not in {"\n", "\r", "\t"}
        )
        if decoded and controls / len(decoded) > 0.01:
            raise AttachmentValidationError("The text file contains binary data.")
