import tempfile
from pathlib import Path
from typing import Union

from fastapi import HTTPException, UploadFile, status

from app.config.setting import settings
from app.utils.document_parser import DocumentParser
from app.utils.fast_document_parser import FastDocumentParser

MAKE_POST_ALLOWED_EXTENSIONS = frozenset(
    {
        "docx",
        "pdf",
        "md",
        "txt",
        "xlsx",
        "xls",
        "csv",
        "png",
        "jpg",
        "jpeg",
    }
)

_FAST_PARSER_EXTENSIONS = frozenset({"pdf", "txt", "plain", "md", "markdown", "csv"})


def _extension_from_upload(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )
    return Path(file.filename).suffix.lower().lstrip(".")


def _validate_extension_for_backend(extension: str) -> None:
    if extension not in MAKE_POST_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(MAKE_POST_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{extension}. Allowed: {allowed}",
        )

    if (
        settings.DOCUMENT_PARSER_BACKEND == "fast"
        and extension not in _FAST_PARSER_EXTENSIONS
    ):
        fast_list = ", ".join(sorted(_FAST_PARSER_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File type '.{extension}' is not supported with "
                f"DOCUMENT_PARSER_BACKEND=fast (supported: {fast_list}). "
                "Set DOCUMENT_PARSER_BACKEND=llama for docx, xlsx, images, etc."
            ),
        )


async def convert_upload_to_text(
    file: UploadFile,
    parser: Union[DocumentParser, FastDocumentParser],
) -> str:
    """Extract text from an uploaded file using the configured document parser."""
    extension = _extension_from_upload(file)
    _validate_extension_for_backend(extension)

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    suffix = f".{extension}"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        return await parser.parse_file_async(tmp_path, extension)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing document: {exc}",
        ) from exc
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
