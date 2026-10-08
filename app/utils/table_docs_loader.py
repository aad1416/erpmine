"""Load full Lyndom table-docs from disk for Text-to-SQL (includes ## Columns)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Tuple

from app.config.setting import settings

logger = logging.getLogger(__name__)

_DESCRIPTION_HEADER = "## Description"
_SENTENCE_END = re.compile(r".*?[.!?](?=\s|$)")


def resolve_table_docs_dir() -> Path:
    """Resolve DB_RAG_TABLE_DOCS_PATH relative to cwd or project root."""
    configured = Path(settings.DB_RAG_TABLE_DOCS_PATH)
    if configured.is_absolute():
        return configured

    candidates = [
        Path.cwd() / configured,
        Path(__file__).resolve().parents[2] / configured,
    ]
    for path in candidates:
        if path.is_dir():
            return path

    return candidates[0]


def load_table_docs_markdown(table_names: List[str]) -> Tuple[str, List[str]]:
    """
    Load full table-doc markdown files for SQL generation.

    Returns:
        (concatenated markdown, list of table names successfully loaded)
    """
    docs_dir = resolve_table_docs_dir()
    if not docs_dir.is_dir():
        logger.error("Table docs directory not found: %s", docs_dir)
        return "", []

    parts: List[str] = []
    loaded: List[str] = []

    for table_name in table_names:
        doc_path = docs_dir / f"{table_name}.md"
        if not doc_path.is_file():
            logger.warning("No table-doc file for '%s' at %s", table_name, doc_path)
            continue
        parts.append(doc_path.read_text(encoding="utf-8"))
        loaded.append(table_name)

    return "\n\n".join(parts), loaded


def _extract_description_section(doc_text: str) -> str:
    """Return the raw text under `## Description`, up to the next `## ` heading."""
    lines = doc_text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == _DESCRIPTION_HEADER:
            body: List[str] = []
            for later in lines[i + 1 :]:
                if later.startswith("## "):
                    break
                body.append(later)
            return "\n".join(body)
    return ""


def _first_sentence(description: str) -> str:
    """Return the first sentence of a (possibly multi-line) description block."""
    flat = " ".join(line.strip() for line in description.strip().splitlines() if line.strip())
    if not flat:
        return ""
    match = _SENTENCE_END.match(flat)
    return (match.group(0) if match else flat).strip()


def build_table_index() -> List[Tuple[str, str]]:
    """One entry per Lyndom table-doc: (table_name, "table_name — first Description sentence").

    A table-doc with no `## Description` section still yields an entry — the line is
    just the table name, never dropped and never raised on.
    """
    docs_dir = resolve_table_docs_dir()
    if not docs_dir.is_dir():
        logger.error("Table docs directory not found: %s", docs_dir)
        return []

    index: List[Tuple[str, str]] = []
    for doc_path in sorted(docs_dir.glob("*.md")):
        table_name = doc_path.stem
        sentence = _first_sentence(
            _extract_description_section(doc_path.read_text(encoding="utf-8"))
        )
        line = f"{table_name} — {sentence}" if sentence else table_name
        index.append((table_name, line))

    return index
