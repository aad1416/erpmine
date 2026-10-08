"""
Inspect parsed markdown and chunk metadata without running the API.

Usage:
  python inspect_chunks_and_metadata.py --file-id <uuid>
  python inspect_chunks_and_metadata.py --path path\\to\\file.pdf

Outputs:
  - parsed_output_inspect.md
  - chunk_dump_inspect.json
"""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Optional

from app.config.setting import settings
from app.utils.document_parser import DocumentParser
from app.utils.markdown_chunker import MarkdownChunker


def _resolve_file_type(
    file_path: str,
    extension: Optional[str],
    mime_type: Optional[str],
) -> str:
    if extension:
        return extension.lower().lstrip(".")
    suffix = Path(file_path).suffix.lstrip(".")
    if suffix:
        return suffix.lower()
    if mime_type and "/" in mime_type:
        return mime_type.split("/")[-1].lower()
    return ""


def _load_from_db(file_id: str) -> tuple[str, str | None, str | None]:
    db_path = Path("storage/main.db")
    if not db_path.exists():
        raise SystemExit(f"DB not found at {db_path}")
    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT path, extension, mime_type FROM files WHERE id = ?",
        (file_id,),
    ).fetchone()
    con.close()
    if not row:
        raise SystemExit("File not found in DB")
    return row


def _build_document_parser() -> DocumentParser:
    return DocumentParser(
        llama_parse_api_key=settings.LLAMA_PARSE_API_KEY,
        language=settings.LLAMA_PARSE_LANGUAGE,
        config_profile=settings.LLAMA_PARSE_CONFIG_PROFILE,
        version=settings.LLAMA_PARSE_VERSION,
    )


def _build_chunker() -> MarkdownChunker:
    if settings.MARKDOWN_CHUNKER_BACKEND == "llamaindex":
        from app.utils.llamaindex_chunker import LlamaIndexMarkdownChunker

        return LlamaIndexMarkdownChunker(
            text_chunk_size=settings.TEXT_CHUNK_SIZE,
            text_chunk_overlap=settings.TEXT_CHUNK_OVERLAP,
            table_max_rows=settings.TABLE_MAX_ROWS,
            table_row_overlap=settings.TABLE_ROW_OVERLAP,
            min_section_tokens=settings.MIN_SECTION_TOKENS,
        )
    return MarkdownChunker(
        text_chunk_size=settings.TEXT_CHUNK_SIZE,
        text_chunk_overlap=settings.TEXT_CHUNK_OVERLAP,
        table_max_rows=settings.TABLE_MAX_ROWS,
        table_row_overlap=settings.TABLE_ROW_OVERLAP,
        min_section_tokens=settings.MIN_SECTION_TOKENS,
    )



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-id", help="File ID from storage/main.db")
    parser.add_argument("--path", help="Path to file on disk")
    parser.add_argument("--document-id", help="Document ID for metadata")
    parser.add_argument("--output-prefix", default="inspect", help="Output file prefix")
    args = parser.parse_args()

    if not args.file_id and not args.path:
        raise SystemExit("Provide --file-id or --path")

    if args.file_id:
        file_path, extension, mime_type = _load_from_db(args.file_id)
    else:
        file_path = args.path
        extension = None
        mime_type = None

    file_type = _resolve_file_type(file_path, extension, mime_type)
    if not file_type:
        raise SystemExit("Could not determine file type from path or DB metadata")

    doc_id = args.document_id or args.file_id or "test-document"
    base_metadata = {
        "document_id": str(doc_id),
        "file_id": str(args.file_id or ""),
        "filename": Path(file_path).name,
        "file_type": file_type,
    }

    doc_parser = _build_document_parser()
    chunker = _build_chunker()

    markdown = doc_parser.parse_file(file_path, file_type)
    md_out = Path(f"parsed_output_{args.output_prefix}.md")
    md_out.write_text(markdown, encoding="utf-8")

    chunks = chunker.chunk_markdown(markdown, base_metadata)

    def token_count(text: str) -> int:
        if hasattr(chunker, "_token_count"):
            return int(chunker._token_count(text))
        return len(text.split())

    output = []
    for idx, chunk in enumerate(chunks, start=1):
        meta = dict(chunk.metadata)
        meta.setdefault("chunk_index", str(idx))
        output.append(
            {
                "chunk_index": idx,
                "token_count": token_count(chunk.text),
                "text": chunk.text,
                "metadata": meta,
            }
        )

    json_out = Path(f"chunk_dump_{args.output_prefix}.json")
    json_out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {md_out} and {json_out}")


if __name__ == "__main__":
    main()
