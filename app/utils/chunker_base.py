import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.parser_constants import ChunkerConstants
from app.utils.table_parser import TableParser

PAGE_MARKER_RE = re.compile(r"<!--\s*PAGE:(\d+)\s*-->|<<<\s*PAGE:(\d+)\s*>>>", re.IGNORECASE)


@dataclass
class Chunk:
    text: str
    metadata: Dict[str, str]


@dataclass
class Section:
    path: List[str]
    blocks: List[Dict[str, Any]] = field(default_factory=list)


class BaseMarkdownChunker:
    """
    Shared base class for MarkdownChunker and LlamaIndexMarkdownChunker.

    Provides all common infrastructure:
      - Tokenization (tiktoken)
      - Text splitting (RecursiveCharacterTextSplitter)
      - Table preparation, composition, and row-based chunking
      - Header prefix generation
      - Page segment splitting
      - Small section merging
    """

    def __init__(
        self,
        text_chunk_size: int = 500,
        text_chunk_overlap: int = 100,
        table_max_rows: int = 50,
        table_row_overlap: int = 0,
        min_section_tokens: int = 50,
        tokenizer: str = "cl100k_base",
    ) -> None:
        # Constants (not exposed to .env)
        self.table_max_tokens = ChunkerConstants.TABLE_MAX_TOKENS
        self.table_token_overlap = ChunkerConstants.TABLE_TOKEN_OVERLAP

        # Configurable parameters
        self.table_max_rows = table_max_rows
        self.table_row_overlap = max(table_row_overlap, 0)
        self.min_section_tokens = min_section_tokens

        self._encoding = tiktoken.get_encoding(tokenizer)
        self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=tokenizer,
            chunk_size=text_chunk_size,
            chunk_overlap=text_chunk_overlap,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
        )

    # ──────────────────────────────────────────────────────────────
    # Page segment splitting
    # ──────────────────────────────────────────────────────────────

    def _split_page_segments(
        self,
        content: str,
        current_page: int,
    ) -> tuple[List[tuple[int, str]], int]:
        """Split *content* on ``<!-- PAGE:N -->`` markers.

        Returns a list of ``(page_number, text)`` tuples and the last
        observed page number.
        """
        if not content:
            return [], current_page

        # Remove CONTINUED_CONTEXT markers that were used by the parser for tracking state
        # but are not needed in the final chunk text and can cause empty "bad" chunks.
        content = re.sub(r"<!--\s*CONTINUED_CONTEXT:.*?-->", "", content, flags=re.IGNORECASE).strip()

        if not content:
            return [], current_page

        segments: List[tuple[int, str]] = []
        page = max(current_page, 1)
        cursor = 0

        for match in PAGE_MARKER_RE.finditer(content):
            before = content[cursor : match.start()].strip()
            if before:
                segments.append((page, before))

            marker_page = match.group(1) or match.group(2)
            if marker_page:
                try:
                    parsed = int(marker_page)
                    if parsed > 0:
                        page = parsed
                except ValueError:
                    pass
            cursor = match.end()

        tail = content[cursor:].strip()
        if tail:
            segments.append((page, tail))

        return segments, page

    # ──────────────────────────────────────────────────────────────
    # Small-section merging
    # ──────────────────────────────────────────────────────────────

    def _merge_small_sections(self, sections: List[Section]) -> List[Section]:
        """Merge sections below *min_section_tokens* into a hierarchy neighbour."""
        if not sections or self.min_section_tokens <= 0:
            return sections

        def section_tokens(section: Section) -> int:
            parts: List[str] = []
            for block in section.blocks:
                content = block.get("content")
                if not content:
                    continue
                if block.get("type") == "table":
                    parts.append("\n".join(content) if isinstance(content, list) else str(content))
                else:
                    parts.append(str(content))
            return self._token_count("\n".join(parts))

        def common_prefix_len(a: List[str], b: List[str]) -> int:
            n = 0
            for left, right in zip(a, b):
                if left != right:
                    break
                n += 1
            return n

        merged: List[Section] = []
        i = 0
        while i < len(sections):
            section = sections[i]
            token_count = section_tokens(section)

            # Never merge a section that contains a table away from itself.
            has_table = any(b.get("type") == "table" for b in section.blocks)
            if has_table and token_count < self.min_section_tokens:
                token_count = self.min_section_tokens

            if token_count >= self.min_section_tokens:
                merged.append(section)
                i += 1
                continue

            prev_section = merged[-1] if merged else None
            next_section = sections[i + 1] if i + 1 < len(sections) else None

            merge_with_prev = False
            if prev_section and next_section:
                prev_score = common_prefix_len(prev_section.path, section.path)
                next_score = common_prefix_len(next_section.path, section.path)
                merge_with_prev = prev_score >= next_score
            elif prev_section:
                merge_with_prev = True

            if merge_with_prev and prev_section:
                prev_section.blocks.extend(section.blocks)
                i += 1
                continue

            if next_section:
                next_section.blocks = section.blocks + next_section.blocks
                if not next_section.path:
                    next_section.path = section.path
                i += 1
                continue

            merged.append(section)
            i += 1

        return merged

    # ──────────────────────────────────────────────────────────────
    # Header prefix
    # ──────────────────────────────────────────────────────────────

    def _header_prefix(self, path: List[str]) -> str:
        """Build a Markdown heading block from a section *path* list."""
        if not path:
            return ""
        lines: List[str] = []
        for i, title in enumerate(path):
            if not title:
                continue
            level = min(i + 1, 6)
            lines.append(f"{'#' * level} {title}")
        if not lines:
            return ""
        return "\n".join(lines) + "\n\n"

    # ──────────────────────────────────────────────────────────────
    # Text chunking
    # ──────────────────────────────────────────────────────────────

    def _chunk_text(
        self,
        text: str,
        metadata: Dict[str, str],
        header_prefix: str = "",
        page: int | None = None,
    ) -> List[Chunk]:
        stripped = text.strip()
        if not stripped:
            return []
        prefix = header_prefix or ""
        chunk_metadata = {**metadata, "chunk_type": "text"}
        if page is not None:
            chunk_metadata["page"] = str(page)
        return [
            Chunk(text=f"{prefix}{chunk}", metadata=dict(chunk_metadata))
            for chunk in self._splitter.split_text(stripped)
        ]

    # ──────────────────────────────────────────────────────────────
    # Table preparation helpers
    # ──────────────────────────────────────────────────────────────

    def _prepare_table_lines(
        self, lines: List[str]
    ) -> tuple[List[str], List[str], List[str]]:
        """Parse raw Markdown table *lines* into (prefix_rows, header_rows, body_rows)."""
        parsed_rows: List[List[str]] = []
        for line in lines:
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            parsed_rows.append(cells)

        if not parsed_rows:
            return [], [], []

        def is_separator(row: List[str]) -> bool:
            if not row:
                return False
            for cell in row:
                if not cell:
                    continue
                if not re.match(r"^:?-{1,}:?$", cell):
                    return False
            return True

        def non_empty_count(row: List[str]) -> int:
            return sum(1 for c in row if c.strip())

        candidates = [
            (idx, row)
            for idx, row in enumerate(parsed_rows)
            if not is_separator(row) and non_empty_count(row) > 0
        ]
        if not candidates:
            header_idx = 0
        else:
            header_idx, _ = max(candidates, key=lambda pair: non_empty_count(pair[1]))

        prefix_lines: List[str] = []
        for row in parsed_rows[:header_idx]:
            if is_separator(row):
                continue
            cells = [c for c in row if c.strip()]
            if cells:
                prefix_lines.append(" ".join(cells))

        header_cells = parsed_rows[header_idx]
        header_cells = [c if c.strip() else "" for c in header_cells]
        header_line = "| " + " | ".join(header_cells) + " |"
        separator_line = "| " + " | ".join(["---"] * len(header_cells)) + " |"

        body_lines: List[str] = []
        for row in parsed_rows[header_idx + 1 :]:
            if is_separator(row):
                continue
            if non_empty_count(row) == 0:
                continue
            body_lines.append("| " + " | ".join(row) + " |")

        return prefix_lines, [header_line, separator_line], body_lines

    def _compose_table_text(
        self, prefix_lines: List[str], header_lines: List[str], body_lines: List[str]
    ) -> str:
        parts: List[str] = []
        if prefix_lines:
            parts.append("\n".join(prefix_lines))
        if header_lines:
            parts.append("\n".join(header_lines))
        if body_lines:
            parts.append("\n".join(body_lines))
        return "\n\n".join(part for part in parts if part)

    # ──────────────────────────────────────────────────────────────
    # Table chunking
    # ──────────────────────────────────────────────────────────────

    def _chunk_table(
        self,
        lines: List[str],
        metadata: Dict[str, str],
        header_prefix: str = "",
        extra_prefix: str = "",
        table_html: str | None = None,
        page: int | None = None,
    ) -> List[Chunk]:
        if not lines:
            return []
        table_id = str(uuid.uuid4())
        prefix_text, header_lines, body_lines = self._prepare_table_lines(lines)
        if extra_prefix:
            extra_lines = [line.strip() for line in extra_prefix.splitlines() if line.strip()]
            prefix_text = extra_lines + prefix_text
        table_text = self._compose_table_text(prefix_text, header_lines, body_lines)
        base_metadata = {**metadata, "chunk_type": "table", "table_id": table_id}
        if page is not None:
            base_metadata["page"] = str(page)

        if table_html:
            if len(table_html) > 25000:
                base_metadata["table_html"] = table_html[:25000] + "...(truncated)"
                base_metadata["table_truncated"] = "true"
            else:
                base_metadata["table_html"] = table_html

        prefix = header_prefix or ""
        if self._token_count(table_text) <= self.table_max_tokens:
            return [Chunk(text=f"{prefix}{table_text}", metadata=base_metadata)]

        header = header_lines
        body = body_lines
        if not body:
            return [Chunk(text=f"{prefix}{table_text}", metadata=base_metadata)]

        chunks: List[Chunk] = []
        start = 0

        while start < len(body):
            rows = body[start : start + self.table_max_rows]
            chunk_text = self._compose_table_text(prefix_text, header, rows)
            while self._token_count(chunk_text) > self.table_max_tokens and len(rows) > 1:
                rows = rows[:-1]
                chunk_text = self._compose_table_text(prefix_text, header, rows)

            chunk_metadata = dict(base_metadata)
            chunk_metadata["row_start"] = str(start + 1)
            chunk_metadata["row_end"] = str(start + len(rows))
            if len(rows) == 1 and self._token_count(chunk_text) > self.table_max_tokens:
                chunk_metadata["overflow"] = "true"
            chunks.append(Chunk(text=f"{prefix}{chunk_text}", metadata=chunk_metadata))

            if start + len(rows) >= len(body):
                break

            overlap_rows = self._table_overlap_rows(rows)
            if overlap_rows >= len(rows):
                overlap_rows = max(len(rows) - 1, 0)
            next_start = start + len(rows) - overlap_rows
            if next_start <= start:
                next_start = start + len(rows)
            start = next_start

        return chunks

    # ──────────────────────────────────────────────────────────────
    # Token helpers
    # ──────────────────────────────────────────────────────────────

    def _token_count(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def _table_overlap_rows(self, rows: List[str]) -> int:
        overlap_rows = min(self.table_row_overlap, len(rows))
        if self.table_token_overlap > 0 and rows:
            tokens = 0
            rows_needed = 0
            for row in reversed(rows):
                tokens += self._token_count(row)
                rows_needed += 1
                if tokens >= self.table_token_overlap:
                    break
            overlap_rows = max(overlap_rows, rows_needed)
        return overlap_rows
