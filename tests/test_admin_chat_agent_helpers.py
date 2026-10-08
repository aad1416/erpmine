"""Lightweight unit checks (stdlib only) for admin chat agent helpers and tool services."""

import asyncio
from unittest import TestCase, main

from app.config.setting import settings
from app.prompts.admin_chat import build_admin_agent_instructions
from app.services.admin_chat_agent_runner import _strip_wrapping_quotes
from app.services.database_query_tool_service import (
    DatabaseQueryToolService,
    _extract_sql_tables,
)
from app.services.document_retrieval_tool_service import DocumentRetrievalToolService


class AdminAgentInstructionsTest(TestCase):
    def test_lists_tools_without_db(self) -> None:
        s = build_admin_agent_instructions("You are helpful.", use_db=False)
        self.assertIn("## Current Persona", s)
        self.assertIn("You are helpful.", s)
        self.assertIn(
            "Tools enabled for this turn: update_persona, retrieve_documents.", s
        )

    def test_lists_tools_with_db(self) -> None:
        s = build_admin_agent_instructions("You are helpful.", use_db=True)
        self.assertIn(
            "Tools enabled for this turn: update_persona, retrieve_documents, query_database.",
            s,
        )


class StripWrappingQuotesTest(TestCase):
    def test_strips_triple_and_single_quotes(self) -> None:
        self.assertEqual(_strip_wrapping_quotes('"""hi there"""'), "hi there")
        self.assertEqual(_strip_wrapping_quotes('"hi there"'), "hi there")
        self.assertEqual(_strip_wrapping_quotes("  plain  "), "plain")
        self.assertEqual(_strip_wrapping_quotes(""), "")


class _FakeRagService:
    def __init__(self, result):
        self._result = result

    async def retrieve_async(self, **kwargs):
        return self._result


class DocumentRetrievalToolServiceTest(TestCase):
    def test_empty_query_returns_error(self) -> None:
        svc = DocumentRetrievalToolService(rag_service=_FakeRagService({}))
        result = asyncio.run(svc.retrieve(query="   ", feature_id=1, top_k=5))
        self.assertEqual(result.content, "Error: empty search query.")
        self.assertEqual(result.sources, [])

    def test_returns_formatted_content_and_sources(self) -> None:
        rag = _FakeRagService(
            {"formatted": "chunk text", "sources": [{"document_id": 1, "chunk_index": 0}]}
        )
        svc = DocumentRetrievalToolService(rag_service=rag)
        result = asyncio.run(svc.retrieve(query="policy", feature_id=1, top_k=5))
        self.assertEqual(result.content, "chunk text")
        self.assertEqual(len(result.sources), 1)

    def test_no_chunks_message(self) -> None:
        svc = DocumentRetrievalToolService(rag_service=_FakeRagService({"formatted": ""}))
        result = asyncio.run(svc.retrieve(query="policy", feature_id=1, top_k=5))
        self.assertEqual(result.content, "(No matching documentation chunks.)")


class DatabaseQueryToolServiceTest(TestCase):
    def test_disabled_setting_short_circuits(self) -> None:
        original = settings.DB_RAG_ENABLED
        settings.DB_RAG_ENABLED = False
        try:
            svc = DatabaseQueryToolService(
                db_rag_retrieval_service=None, db_rag_query_service=None
            )
            result = asyncio.run(
                svc.query(question="q", feature_id=1, store_id=None, user_accesses=[])
            )
            self.assertIn("disabled", result.content)
            self.assertEqual(result.audit, [])
        finally:
            settings.DB_RAG_ENABLED = original

    def test_missing_lyndom_repo_message(self) -> None:
        original = settings.DB_RAG_ENABLED
        settings.DB_RAG_ENABLED = True
        try:
            svc = DatabaseQueryToolService(
                db_rag_retrieval_service=None, db_rag_query_service=None, lyndom_repo=None
            )
            result = asyncio.run(
                svc.query(question="q", feature_id=1, store_id=None, user_accesses=[])
            )
            self.assertIn("not configured", result.content)
        finally:
            settings.DB_RAG_ENABLED = original

    def test_extract_sql_tables(self) -> None:
        sql = "SELECT * FROM orders o JOIN order_items i ON o.id = i.order_id"
        self.assertEqual(_extract_sql_tables(sql), {"orders", "order_items"})


if __name__ == "__main__":
    main()
