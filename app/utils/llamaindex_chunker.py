import uuid
from typing import Any, Dict, List

from llama_index.core import Document
from llama_index.core.node_parser import MarkdownElementNodeParser, MarkdownNodeParser
from llama_index.core.node_parser.text.langchain import LangchainNodeParser
from llama_index.core.schema import IndexNode, NodeRelationship, TextNode

from app.utils.chunker_base import BaseMarkdownChunker, Chunk, Section
from app.utils.table_parser import TableParser


class LlamaIndexMarkdownChunker(BaseMarkdownChunker):
    """
    AST-based Markdown chunker using LlamaIndex's ``MarkdownNodeParser``
    and ``MarkdownElementNodeParser``.

    All shared chunking and table-splitting logic lives in ``BaseMarkdownChunker``.
    This class only contains the LlamaIndex-specific AST traversal.
    """

    def __init__(
        self,
        text_chunk_size: int = 500,
        text_chunk_overlap: int = 100,
        table_max_rows: int = 50,
        table_row_overlap: int = 0,
        min_section_tokens: int = 50,
        tokenizer: str = "cl100k_base",
        header_path_separator: str = " / ",
    ) -> None:
        super().__init__(
            text_chunk_size=text_chunk_size,
            text_chunk_overlap=text_chunk_overlap,
            table_max_rows=table_max_rows,
            table_row_overlap=table_row_overlap,
            min_section_tokens=min_section_tokens,
            tokenizer=tokenizer,
        )
        self.header_path_separator = header_path_separator.strip() or "/"

        lc_splitter = self._splitter  # reuse the splitter built by BaseMarkdownChunker
        self._text_splitter = LangchainNodeParser(lc_splitter=lc_splitter)
        self._markdown_parser = MarkdownNodeParser(
            include_metadata=True,
            include_prev_next_rel=False,
            header_path_separator=self.header_path_separator,
        )
        self._element_parser = _NoSummaryMarkdownElementNodeParser(
            include_metadata=True,
            include_prev_next_rel=False,
        )

    # ──────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────

    def chunk_markdown(self, markdown: str, metadata: Dict[str, str]) -> List[Chunk]:
        base_doc = Document(text=markdown)
        section_nodes = self._markdown_parser.get_nodes_from_documents([base_doc])
        sections = self._nodes_to_sections(section_nodes)
        sections = self._merge_small_sections(sections)

        chunks: List[Chunk] = []
        for section in sections:
            section_metadata = (
                {**metadata, "section_path": " / ".join(section.path)}
                if section.path
                else dict(metadata)
            )
            section_path = section_metadata.get("section_path", "")
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
                    if (
                        self.min_section_tokens > 0
                        and self._token_count(combined) < self.min_section_tokens
                        and chunks
                    ):
                        last_chunk = chunks[-1]
                        last_section = last_chunk.metadata.get("section_path", "")
                        last_page = last_chunk.metadata.get("page")
                        current_page = str(page) if page is not None else None
                        if last_section == section_path and last_page == current_page:
                            last_chunk.text = f"{last_chunk.text}\n\n{combined}"
                            return
                    chunks.extend(
                        self._chunk_text(
                            combined,
                            section_metadata,
                            header_prefix,
                            page=page,
                        )
                    )

            for block in section.blocks:
                block_page_raw = block.get("page")
                block_page = int(block_page_raw) if block_page_raw is not None else None

                if block["type"] == "table":
                    table_lines = block.get("content") or []
                    if not table_lines:
                        continue

                    if (
                        text_buffer
                        and text_buffer_page is not None
                        and block_page is not None
                        and block_page != text_buffer_page
                    ):
                        flush_text_buffer()

                    table_str = "\n".join(table_lines)
                    table_tokens = self._token_count(table_str)
                    if table_tokens < self.min_section_tokens:
                        if text_buffer_page is None:
                            text_buffer_page = block_page
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
                        chunks.extend(
                            self._chunk_table(
                                table_lines,
                                section_metadata,
                                header_prefix=header_prefix,
                                extra_prefix=extra_prefix,
                                page=block_page,
                            )
                        )
                else:
                    content = block["content"].strip()
                    if content:
                        if (
                            text_buffer
                            and text_buffer_page is not None
                            and block_page is not None
                            and block_page != text_buffer_page
                        ):
                            flush_text_buffer()
                        if text_buffer_page is None:
                            text_buffer_page = block_page
                        text_buffer.append(content)

            flush_text_buffer()

        return chunks

    # ──────────────────────────────────────────────────────────────
    # LlamaIndex-specific AST traversal
    # ──────────────────────────────────────────────────────────────

    def _nodes_to_sections(self, nodes: List[TextNode]) -> List[Section]:
        sections: List[Section] = []
        current_page = 1
        for node in nodes:
            header_path = ""
            if isinstance(node.metadata, dict):
                header_path = node.metadata.get("header_path") or ""
            path = [
                part.strip()
                for part in header_path.split(self.header_path_separator)
                if part.strip()
            ]
            heading = self._extract_heading(node)
            if heading:
                path.append(heading)
            elements = self._element_parser.get_nodes_from_node(node)
            blocks: List[Dict[str, Any]] = []
            for element in elements:
                content = self._node_text(element)
                if not content:
                    continue
                segments, current_page = self._split_page_segments(content, current_page)
                for page_number, segment in segments:
                    if not segment:
                        continue
                    if isinstance(element, IndexNode):
                        table_lines = self._table_lines(segment)
                        if table_lines:
                            blocks.append(
                                {
                                    "type": "table",
                                    "content": table_lines,
                                    "page": page_number,
                                }
                            )
                    else:
                        blocks.append(
                            {
                                "type": "text",
                                "content": segment,
                                "page": page_number,
                            }
                        )
            if blocks:
                sections.append(Section(path=path, blocks=blocks))
        return sections

    def _node_text(self, node: Any) -> str:
        if hasattr(node, "get_content"):
            try:
                return node.get_content()
            except Exception:
                pass
        text = getattr(node, "text", None)
        if text:
            return str(text)
        return str(node) if node is not None else ""

    def _extract_heading(self, node: TextNode) -> str:
        text = getattr(node, "text", "") or ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if stripped:
                break
        return ""

    def _table_lines(self, text: str) -> List[str]:
        if "<table" in text.lower():
            text = TableParser.html_to_markdown(text) or text
        return [line for line in text.splitlines() if line.strip()]


class _NoSummaryMarkdownElementNodeParser(MarkdownElementNodeParser):
    """Markdown element parser without table summarization (avoids LLM dependency)."""

    def get_nodes_from_node(self, node: TextNode) -> List[Any]:
        elements = self.extract_elements(
            node.get_content(), table_filters=[self.filter_table], node_id=node.node_id
        )
        if hasattr(self, "extract_html_tables"):
            elements = self.extract_html_tables(elements)
        nodes: List[Any] = []
        for element in elements:
            content = str(element.element).strip() if element.element is not None else ""
            if not content:
                continue
            if element.type in ("table", "table_text"):
                node_id = str(uuid.uuid4())
                nodes.append(IndexNode(text=content, index_id=node_id))
            else:
                nodes.append(TextNode(text=content))

        source_document = node.source_node or node.as_related_node_info()
        for n in nodes:
            n.relationships[NodeRelationship.SOURCE] = source_document
            n.metadata.update(node.metadata)
        return nodes
