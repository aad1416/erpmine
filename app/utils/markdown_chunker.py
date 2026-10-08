from typing import Any, Dict, List

from markdown_it import MarkdownIt

from app.utils.chunker_base import BaseMarkdownChunker, Chunk, Section
from app.utils.table_parser import TableParser


class MarkdownChunker(BaseMarkdownChunker):
    """
    AST-based Markdown chunker using ``markdown-it-py``.

    Parses the Markdown token stream directly to group content into
    logical ``Section`` objects, then delegates all chunking and table
    splitting to ``BaseMarkdownChunker``.
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
        super().__init__(
            text_chunk_size=text_chunk_size,
            text_chunk_overlap=text_chunk_overlap,
            table_max_rows=table_max_rows,
            table_row_overlap=table_row_overlap,
            min_section_tokens=min_section_tokens,
            tokenizer=tokenizer,
        )
        self._md = MarkdownIt("gfm-like")

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def chunk_markdown(self, markdown: str, metadata: Dict[str, str]) -> List[Chunk]:
        chunks: List[Chunk] = []
        raw_sections = self._sections(self._md.parse(markdown))
        sections = self._merge_small_sections(raw_sections)
        current_page = 1

        for section in sections:
            section_metadata = (
                {**metadata, "section_path": " / ".join(section.path)}
                if section.path
                else dict(metadata)
            )
            header_prefix = self._header_prefix(section.path)
            text_buffer: List[str] = []
            text_buffer_page: int | None = None

            def flush_text_buffer() -> None:
                nonlocal text_buffer_page
                if not text_buffer:
                    return
                combined = "\n\n".join(text_buffer).strip()
                page = text_buffer_page
                text_buffer.clear()
                text_buffer_page = None
                if combined:
                    chunks.extend(
                        self._chunk_text(
                            combined,
                            section_metadata,
                            header_prefix,
                            page=page,
                        )
                    )

            for block in section.blocks:
                if block["type"] == "table":
                    table_lines = block.get("content") or []
                    if not table_lines:
                        continue
                    raw_table = "\n".join(table_lines)
                    segments, current_page = self._split_page_segments(
                        raw_table, current_page
                    )
                    for segment_page, segment in segments:
                        segment_lines = [line for line in segment.splitlines() if line.strip()]
                        if not segment_lines:
                            continue

                        if (
                            text_buffer
                            and text_buffer_page is not None
                            and segment_page != text_buffer_page
                        ):
                            flush_text_buffer()

                        table_str = "\n".join(segment_lines)
                        table_tokens = self._token_count(table_str)

                        if table_tokens < self.min_section_tokens:
                            if text_buffer_page is None:
                                text_buffer_page = segment_page
                            text_buffer.append(table_str)
                        else:
                            extra_prefix = ""
                            if text_buffer:
                                buffer_text = "\n\n".join(text_buffer).strip()
                                if (
                                    buffer_text
                                    and self._token_count(buffer_text)
                                    < self.min_section_tokens
                                ):
                                    extra_prefix = buffer_text
                                    text_buffer.clear()
                                    text_buffer_page = None
                                else:
                                    flush_text_buffer()

                            table_html = block.get("table_html")
                            chunks.extend(
                                self._chunk_table(
                                    segment_lines,
                                    section_metadata,
                                    header_prefix=header_prefix,
                                    extra_prefix=extra_prefix,
                                    table_html=table_html,
                                    page=segment_page,
                                )
                            )
                else:
                    content = block["content"].strip()
                    if not content:
                        continue

                    segments, current_page = self._split_page_segments(content, current_page)
                    for segment_page, segment in segments:
                        if not segment:
                            continue
                        if (
                            text_buffer
                            and text_buffer_page is not None
                            and segment_page != text_buffer_page
                        ):
                            flush_text_buffer()
                        if text_buffer_page is None:
                            text_buffer_page = segment_page
                        text_buffer.append(segment)

            flush_text_buffer()

        return chunks

    # ──────────────────────────────────────────────────────────────
    # markdown-it-py token traversal
    # ──────────────────────────────────────────────────────────────

    def _sections(self, tokens: List) -> List[Section]:
        sections: List[Section] = []
        stack: List[str] = []
        current = Section(path=[])
        i = 0

        while i < len(tokens):
            token = tokens[i]
            if token.type == "heading_open":
                if current.blocks:
                    sections.append(current)
                level = int(token.tag[1])
                heading = ""
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading = tokens[i + 1].content
                stack = stack[: level - 1] + [heading]
                current = Section(path=list(stack))
                i += 3
            elif token.type == "table_open":
                table_tokens = []
                while i < len(tokens) and tokens[i].type != "table_close":
                    table_tokens.append(tokens[i])
                    i += 1
                i += 1
                current.blocks.append(
                    {"type": "table", "content": self._table_lines(table_tokens)}
                )
            elif token.type == "fence":
                current.blocks.append(
                    {
                        "type": "text",
                        "content": f"```{token.info}\n{token.content}```",
                    }
                )
                i += 1
            elif token.type == "code_block":
                current.blocks.append(
                    {"type": "text", "content": f"```\n{token.content}```"}
                )
                i += 1
            elif token.type == "html_block":
                current.blocks.extend(self._split_html_block(token.content))
                i += 1
            elif token.type == "paragraph_open":
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    current.blocks.append(
                        {"type": "text", "content": tokens[i + 1].content}
                    )
                i += 3
            elif token.type in ("bullet_list_open", "ordered_list_open"):
                content, next_index = self._extract_list(tokens, i)
                current.blocks.append({"type": "text", "content": content})
                i = next_index
            elif token.type == "blockquote_open":
                content = self._extract_blockquote(tokens, i)
                current.blocks.append({"type": "text", "content": content})
                while i < len(tokens) and tokens[i].type != "blockquote_close":
                    i += 1
                i += 1
            else:
                i += 1

        if current.blocks:
            sections.append(current)

        return sections

    def _extract_list(self, tokens: List, start: int) -> tuple[str, int]:
        lines, next_index = self._parse_list(tokens, start, depth=0)
        return "\n".join(lines), next_index

    def _parse_list(
        self, tokens: List, index: int, depth: int
    ) -> tuple[List[str], int]:
        list_token = tokens[index]
        ordered = list_token.type == "ordered_list_open"
        start_number = 1
        if ordered and hasattr(list_token, "attrGet"):
            raw_start = list_token.attrGet("start")
            if raw_start:
                try:
                    start_number = int(raw_start)
                except ValueError:
                    start_number = 1

        number = start_number
        lines: List[str] = []
        index += 1

        while index < len(tokens):
            token = tokens[index]
            if token.type in ("bullet_list_close", "ordered_list_close"):
                index += 1
                break
            if token.type == "list_item_open":
                item_lines, index, number = self._parse_list_item(
                    tokens, index, depth, ordered, number
                )
                lines.extend(item_lines)
                continue
            index += 1

        return lines, index

    def _parse_list_item(
        self,
        tokens: List,
        index: int,
        depth: int,
        ordered: bool,
        number: int,
    ) -> tuple[List[str], int, int]:
        index += 1
        item_parts: List[str] = []
        nested_lines: List[str] = []

        while index < len(tokens):
            token = tokens[index]
            if token.type == "list_item_close":
                index += 1
                break
            if token.type in ("bullet_list_open", "ordered_list_open"):
                nested, index = self._parse_list(tokens, index, depth + 1)
                nested_lines.extend(nested)
                continue
            if token.type == "inline":
                item_parts.append(token.content)
            elif token.type == "fence":
                item_parts.append(f"```{token.info}\n{token.content}```")
            elif token.type == "code_block":
                item_parts.append(token.content)
            elif token.type == "html_block":
                item_parts.append(token.content)
            index += 1

        marker = f"{number}." if ordered else "-"
        indent = "  " * depth
        text = " ".join(
            part.strip() for part in item_parts if part and part.strip()
        )
        line = f"{indent}{marker} {text}" if text else f"{indent}{marker}"
        lines = [line]
        lines.extend(nested_lines)
        if ordered:
            number += 1
        return lines, index, number

    def _extract_blockquote(self, tokens: List, start: int) -> str:
        lines = []
        for token in tokens[start:]:
            if token.type == "blockquote_close":
                break
            if token.type == "inline":
                lines.append(f"> {token.content}")
        return "\n".join(lines)

    def _split_html_block(self, html: str) -> List[Dict[str, Any]]:
        import re as _re
        if "<table" not in html.lower():
            return [{"type": "text", "content": html}]

        blocks: List[Dict[str, Any]] = []
        last_end = 0
        for match in _re.finditer(
            r"<table[^>]*>.*?</table>",
            html,
            flags=_re.DOTALL | _re.IGNORECASE,
        ):
            prefix = html[last_end : match.start()]
            if prefix.strip():
                blocks.append({"type": "text", "content": prefix.strip()})

            table_html = match.group(0)
            table_markdown = TableParser.html_to_markdown(table_html)
            table_lines = table_markdown.split("\n") if table_markdown else []

            if table_lines:
                blocks.append(
                    {
                        "type": "table",
                        "content": table_lines,
                        "table_html": table_html,
                    }
                )
            else:
                blocks.append({"type": "text", "content": table_html})

            last_end = match.end()

        suffix = html[last_end:]
        if suffix.strip():
            blocks.append({"type": "text", "content": suffix.strip()})

        return blocks or [{"type": "text", "content": html}]

    def _table_lines(self, tokens: List) -> List[str]:
        lines: List[str] = []
        row: List[str] = []
        for token in tokens:
            if token.type == "inline":
                row.append(token.content.replace("|", "\\|"))
            elif token.type == "tr_close" and row:
                lines.append("| " + " | ".join(row) + " |")
                if len(lines) == 1:
                    lines.append("| " + " | ".join(["---"] * len(row)) + " |")
                row = []
        return lines
