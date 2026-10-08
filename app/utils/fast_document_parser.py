import asyncio
import datetime
import logging
import re
from pathlib import Path
from typing import Final, Any, Optional

logger = logging.getLogger(__name__)

import pandas as pd

from app.utils.table_parser import TableParser


class FastParserConstants:
    """Stable configuration constants for the fast (pymupdf4llm) parser.

    These are intentionally kept as code-level constants rather than env
    settings because they represent carefully tuned heuristics for clean
    PDF-to-Markdown conversion and should not be casually overridden at
    deployment time.
    """

    # Minimum font size to include in output.
    # Text smaller than this (e.g. watermarks, copyright micro-print) is dropped.
    FONTSIZE_LIMIT: Final[float] = 3.0

    # If True, transparent text (hidden OCR layers) would be included.
    # Keep False to skip such hidden/invisible text artefacts.
    IGNORE_ALPHA: Final[bool] = False

    # Attempt to detect page background colour so that fill-only vectors
    # matching it are ignored, keeping the output cleaner.
    DETECT_BG_COLOR: Final[bool] = True

    # Strip repetitive page-level headers (document title, logo area, etc.)
    HEADER: Final[bool] = False

    # Strip repetitive page-level footers (page numbers, confidentiality notices)
    FOOTER: Final[bool] = False

    # Disable OCR entirely — we target native, text-based PDFs.
    # Pages with no selectable text will simply return empty strings.
    USE_OCR: Final[bool] = False

    # Keep output as a single continuous Markdown string (enables page_separators)
    PAGE_CHUNKS: Final[bool] = False

    # Inject '--- end of page=N ---' markers between pages (0-based N)
    PAGE_SEPARATORS: Final[bool] = True

    # Do not extract images to disk or embed them as base64
    WRITE_IMAGES: Final[bool] = False


# Regex that matches the pymupdf4llm page separator format
# Example: "--- end of page.page_number=1 ---" or "--- end of page=1 ---"
_FAST_PARSER_SEP_RE = re.compile(r"---\s*end\s+of\s+page(?:.*?)\s*=\s*(\d+)\s*---", re.IGNORECASE)


def _normalize_page_separators(text: str) -> str:
    """Convert pymupdf4llm separators to the project-standard <!-- PAGE:N --> format.

    pymupdf4llm emits:  ``--- end of page.page_number=N ---`` (N is 1-based)
    Project standard:   ``<!-- PAGE:N -->``          (N is **1-based**)
    """

    def _replacer(match: re.Match) -> str:
        # pymupdf4llm's marker indicates the END of the current page.
        # So we increment it by 1 to tell the downstream chunker what the NEXT page is.
        page_num = int(match.group(1))
        next_page = page_num + 1
        return f"<!-- PAGE:{next_page} -->"

    return _FAST_PARSER_SEP_RE.sub(_replacer, text)


class FastDocumentParser:
    """Local, API-free document parser backed by ``pymupdf4llm``.

    Designed as a drop-in alternative to ``DocumentParser`` (LlamaParse).
    Exposes the same public interface:

    * ``parse_file(file_path, file_type) -> str``
    * ``parse_file_async(file_path, file_type) -> str``

    Supported file types
    --------------------
    * **pdf** — parsed with ``pymupdf4llm.to_markdown()``
    * **docx** — parsed with Microsoft ``MarkItDown``
    * **xls, xlsx, xlsb, xlsm** — parsed with ``python-calamine`` (faithful, zero-normalization)
    * **csv** — pandas → Markdown table
    * **txt, plain** — local plain-text parser
    * **md, markdown** — read directly, normalize Markdown
    * **doc, png, jpg, jpeg, tiff, webp** — Cloud fallback parser (requires API key)

    Unsupported types
    -----------------
    Other formats (pptx, etc.) raise a ``ValueError`` indicating the file is unsupported.

    Page separator contract
    -----------------------
    The output of every ``parse_*`` method uses the project-standard separator
    ``<!-- PAGE:N -->`` (1-based) so that downstream chunkers work identically
    in both ``llama`` and ``fast`` modes.
    """

    def __init__(self, llama_fallback_parser: Optional[Any] = None) -> None:
        # No API keys or runtime config — most tuning comes from FastParserConstants.
        self._llama_fallback = llama_fallback_parser

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def parse_file(self, file_path: str, file_type: str) -> str:
        """Synchronously parse a file and return a normalised Markdown string."""
        return self._dispatch(file_path, file_type)

    async def parse_file_async(self, file_path: str, file_type: str) -> str:
        """Asynchronously parse a file.

        Third-party parsers like pymupdf4llm, calamine, and MarkItDown have no native
        async API, so their file I/O operations are offloaded to a thread pool via
        ``asyncio.to_thread``. Text/CSV paths are fast enough to run inline.
        Images use native async httpx via the fallback.
        """
        normalized_type = (file_type or "").lower()
        
        # Intercept legacy formats and images to use the native async LlamaParse fallback
        if normalized_type in {"doc", "png", "jpg", "jpeg", "tiff", "webp"}:
            return await self._parse_with_llama_fallback_async(file_path, file_type)

        # All other formats (pdf, docx, excel, csv, txt) use synchronous third-party 
        # parsers, so we offload their routing and execution to a thread pool.
        return await asyncio.to_thread(self._dispatch, file_path, file_type)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal routing
    # ──────────────────────────────────────────────────────────────────────────

    def _dispatch(self, file_path: str, file_type: str) -> str:
        normalized_type = (file_type or "").lower()

        if normalized_type in {"txt", "plain"}:
            return self._parse_plain_text(file_path)

        if normalized_type in {"md", "markdown"}:
            return self._normalize_markdown(self._read_text_file(file_path))

        if normalized_type == "csv":
            return self._parse_csv(file_path)

        if normalized_type == "pdf":
            return self._parse_pdf(file_path)

        if normalized_type == "docx":
            return self._parse_word(file_path)

        if normalized_type in {"xls", "xlsx", "xlsb", "xlsm"}:
            return self._parse_excel(file_path)

        if normalized_type in {"doc", "png", "jpg", "jpeg", "tiff", "webp"}:
            return self._parse_with_llama_fallback(file_path, file_type)

        # All unsupported formats (pptx, etc.)
        raise ValueError(
            f"The file format '{file_type}' is not supported. "
            "Please convert your document to a supported format (e.g., PDF, DOCX) and try again."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PDF parsing via pymupdf4llm
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_pdf(self, file_path: str) -> str:
        """Convert a PDF to Markdown using pymupdf4llm, then normalise separators."""
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise ImportError(
                "pymupdf4llm is not installed but DOCUMENT_PARSER_BACKEND=fast. "
                "Install it with: pip install pymupdf4llm"
            ) from exc

        raw_md: str = pymupdf4llm.to_markdown(
            doc=file_path,
            # ── Page handling ────────────────────────────────────────────────
            # Keep output as a single continuous string so page_separators works
            page_chunks=FastParserConstants.PAGE_CHUNKS,
            # Inject '--- end of page=N ---' markers (0-based) between pages
            page_separators=FastParserConstants.PAGE_SEPARATORS,
            # ── Images ───────────────────────────────────────────────────────
            # Do not write images to disk or embed them as base64 in the output
            write_images=FastParserConstants.WRITE_IMAGES,
            # ── OCR ──────────────────────────────────────────────────────────
            # Disable OCR entirely; scanned/image-only pages will be empty
            use_ocr=FastParserConstants.USE_OCR,
            # ── Text quality & cleanup ────────────────────────────────────────
            # Strip repetitive page headers (logos, document titles)
            header=FastParserConstants.HEADER,
            # Strip repetitive page footers (page numbers, confidentiality notices)
            footer=FastParserConstants.FOOTER,
            # Ignore text smaller than this point size (watermarks, micro-print)
            fontsize_limit=FastParserConstants.FONTSIZE_LIMIT,
            # Do not include transparent/hidden text layers
            ignore_alpha=FastParserConstants.IGNORE_ALPHA,
            # Use background colour detection to clean vector artefacts
            detect_bg_color=FastParserConstants.DETECT_BG_COLOR,
        )

        # Convert pymupdf4llm's 0-based "--- end of page=N ---" markers into the
        # project-standard 1-based "<!-- PAGE:N -->" format used by LlamaParse,
        # so that chunkers downstream see a single, consistent format.
        normalised = _normalize_page_separators(raw_md)
        return normalised.strip()

    # ──────────────────────────────────────────────────────────────────────────
    # Word parsing via MarkItDown
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_word(self, file_path: str) -> str:
        """Convert Word document to Markdown using Microsoft MarkItDown."""
        try:
            from markitdown import MarkItDown
        except ImportError as exc:
            raise ImportError(
                "markitdown is not installed but DOCUMENT_PARSER_BACKEND=fast. "
                "Install it with: pip install 'markitdown[docx]'"
            ) from exc

        md = MarkItDown()
        try:
            result = md.convert(file_path)
        except Exception as e:
            raise ValueError(f"Failed to read or parse Word document '{file_path}'. The file may be corrupted: {e}") from e
            
        return self._normalize_markdown(result.text_content)

    # ──────────────────────────────────────────────────────────────────────────
    # Excel parsing via python-calamine
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_excel(self, file_path: str) -> str:
        """Convert Excel workbook to Markdown tables using python-calamine."""
        try:
            from python_calamine import CalamineWorkbook
        except ImportError as exc:
            raise ImportError(
                "python-calamine is not installed but DOCUMENT_PARSER_BACKEND=fast. "
                "Install it with: pip install python-calamine"
            ) from exc

        try:
            workbook = CalamineWorkbook.from_path(file_path)
        except Exception as e:
            raise ValueError(f"Failed to read Excel file '{file_path}': {e}") from e

        sheet_markdowns = []
        
        for sheet_name in workbook.sheet_names:
            try:
                sheet = workbook.get_sheet_by_name(sheet_name)
                # skip_empty_area automatically bounds the data correctly
                rows = sheet.to_python(skip_empty_area=True)
            except Exception as e:
                logger.warning(f"Failed to parse Excel sheet '{sheet_name}' in {file_path}: {e}")
                continue
                
            if not rows:
                continue

            max_cols = max(len(row) for row in rows)
            
            # Format the header
            header_cells = self._sanitize_excel_row(rows[0], max_cols)
            lines = [
                f"## {sheet_name}",
                "",
                "| " + " | ".join(header_cells) + " |",
                "| " + " | ".join(["---"] * max_cols) + " |"
            ]
            
            # Format body rows
            for row in rows[1:]:
                body_cells = self._sanitize_excel_row(row, max_cols)
                lines.append("| " + " | ".join(body_cells) + " |")

            sheet_markdowns.append("\n".join(lines))

        if not sheet_markdowns:
            raise ValueError(f"Failed to extract any usable data from Excel file '{file_path}'. All sheets were empty or failed to parse.")

        return "\n\n".join(sheet_markdowns)

    def _sanitize_excel_row(self, row: list[Any], max_cols: int) -> list[str]:
        cells = []
        for i in range(max_cols):
            val = row[i] if i < len(row) else ""
            if val is None:
                cells.append("")
            elif isinstance(val, (datetime.date, datetime.datetime)):
                cells.append(val.isoformat())
            elif isinstance(val, bool):
                cells.append("TRUE" if val else "FALSE")
            else:
                str_val = str(val)
                # Sanitize newlines and pipes for Markdown table syntax
                str_val = str_val.replace("\n", "<br>").replace("\r", "")
                str_val = str_val.replace("|", "\\|")
                cells.append(str_val)
        return cells

    # ──────────────────────────────────────────────────────────────────────────
    # Cloud Fallback via LlamaParse (.doc, images)
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_with_llama_fallback(self, file_path: str, file_type: str) -> str:
        if not self._llama_fallback:
            raise ValueError(
                f"The file format '{file_type}' requires cloud processing, which is currently disabled. "
                "Please convert it to a modern format (e.g., PDF, DOCX) or contact the administrator."
            )
        return self._llama_fallback.parse_file(file_path, file_type)

    async def _parse_with_llama_fallback_async(self, file_path: str, file_type: str) -> str:
        if not self._llama_fallback:
            raise ValueError(
                f"The file format '{file_type}' requires cloud processing, which is currently disabled. "
                "Please convert it to a modern format (e.g., PDF, DOCX) or contact the administrator."
            )
        return await self._llama_fallback.parse_file_async(file_path, file_type)

    # ──────────────────────────────────────────────────────────────────────────
    # Plain-text / Markdown / CSV helpers  (mirrors DocumentParser logic)
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_plain_text(self, file_path: str) -> str:
        text = self._read_text_file(file_path)
        return self._parse_plain_text_content(text)

    def _parse_plain_text_content(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = []
        current: list[str] = []

        for line in text.split("\n"):
            stripped = line.strip()
            if self._is_structural(stripped):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                paragraphs.append(stripped)
            elif not stripped:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
            else:
                current.append(stripped)

        if current:
            paragraphs.append(" ".join(current))

        return "\n\n".join(paragraphs)

    def _is_structural(self, line: str) -> bool:
        if not line:
            return False
        if re.match(r"^[-*+]\s", line) or re.match(r"^\d+\.\s", line):
            return True
        if line.startswith("#") or line.startswith(">"):
            return True
        if line.startswith("```") or line.startswith("~~~"):
            return True
        return False

    def _parse_csv(self, file_path: str) -> str:
        dataframe = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        return dataframe.to_markdown(index=False)

    def _normalize_markdown(self, text: str) -> str:
        """Minimal Markdown normalisation (HTML table conversion if needed)."""
        if "<table" in text.lower():
            text = TableParser.convert_html_tables_in_text(text)
        return text.strip()

    def _read_text_file(self, file_path: str) -> str:
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")
