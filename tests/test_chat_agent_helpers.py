"""Lightweight unit checks (stdlib only) for chat agent helpers."""

from unittest import TestCase, main

from app.prompts.chat_agent import build_agent_instructions, build_run_input
from app.services.chat_sdk_model import supports_openai_agents_sdk


class ChatAgentHelpersTest(TestCase):
    def test_supports_openai_models(self) -> None:
        self.assertTrue(supports_openai_agents_sdk("gpt-4o"))
        self.assertTrue(supports_openai_agents_sdk("gpt-5-mini"))
        self.assertTrue(supports_openai_agents_sdk("o3-mini"))
        self.assertFalse(supports_openai_agents_sdk("claude-3-5-sonnet"))
        self.assertFalse(supports_openai_agents_sdk("gemini-2.0-flash"))

    def test_build_agent_instructions_lists_tools(self) -> None:
        s = build_agent_instructions("You are helpful.", use_rag=True, use_db=False)
        self.assertIn("Tools enabled for this turn: retrieve_documents.", s)
        s2 = build_agent_instructions("You are helpful.", use_rag=False, use_db=True)
        self.assertIn("Tools enabled for this turn: query_database.", s2)
        s3 = build_agent_instructions("You are helpful.", use_rag=False, use_db=False)
        self.assertIn("No retrieval tools are enabled", s3)

    def test_build_run_input_includes_query(self) -> None:
        class M:
            role = "user"
            content = "hi"

        out = build_run_input([M], "current?")
        self.assertIn("Chat History", out)
        self.assertIn("Current Query", out)
        self.assertIn("current?", out)

    def test_build_run_input_replays_table_output_with_full_sql(self) -> None:
        class M:
            role = "assistant"
            content = "Here are the top vendors."
            attachments = [
                {
                    "kind": "table",
                    "title": "Top vendors",
                    "columns": [{"key": "vendor", "label": "Vendor", "type": "string"}],
                    "rows": [["Acme"]] * 30,
                    "row_count": 143,
                    "truncated": True,
                    "provenance": {
                        "sql": "SELECT vendor_name FROM vendors WHERE store_id = 'store-9'",
                        "transforms": [],
                        "row_count": 143,
                        "generated_at": "2026-09-15T00:00:00Z",
                    },
                }
            ]

        out = build_run_input([M], "current?")
        self.assertIn(
            '[Output: table "Top vendors" — 143 rows (30 shown) — '
            "SQL: SELECT vendor_name FROM vendors WHERE store_id = 'store-9']",
            out,
        )

    def test_build_run_input_replays_chart_output_with_transform_chain(self) -> None:
        class M:
            role = "assistant"
            content = "Here is the chart."
            attachments = [
                {
                    "kind": "chart",
                    "title": "Top vendors",
                    "spec": {
                        "type": "bar",
                        "title": "Top vendors",
                        "x": {"values": ["Acme", "Other"]},
                        "series": [{"name": "Value", "values": [1.0, 2.0]}],
                    },
                    "provenance": {
                        "sql": "SELECT vendor_name, total FROM vendors",
                        "transforms": [{"transform": "top_n", "params": {"n": 5}}],
                        "row_count": 2,
                        "generated_at": "2026-09-15T00:00:00Z",
                    },
                }
            ]

        out = build_run_input([M], "current?")
        self.assertIn(
            '[Output: chart "Top vendors" — bar, 2 categories × 1 series — '
            "via top_n — SQL: SELECT vendor_name, total FROM vendors]",
            out,
        )

    def test_build_run_input_replays_file_output(self) -> None:
        class M:
            role = "assistant"
            content = "Here is the export."
            attachments = [
                {
                    "kind": "file",
                    "title": "Customers",
                    "file_id": "f-1",
                    "filename": "customers-2026.xlsx",
                    "mime_type": (
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    ),
                    "size": 4096,
                    "provenance": {
                        "sql": "SELECT * FROM clients",
                        "transforms": [],
                        "row_count": 143,
                        "generated_at": "2026-09-15T00:00:00Z",
                    },
                }
            ]

        out = build_run_input([M], "current?")
        self.assertIn(
            '[Output: file "Customers" — customers-2026.xlsx, 143 rows — '
            "SQL: SELECT * FROM clients]",
            out,
        )

    def test_build_run_input_skips_attachments_on_user_messages(self) -> None:
        class M:
            role = "user"
            content = "hi"
            attachments = [{"kind": "table", "title": "should not replay"}]

        out = build_run_input([M], "current?")
        self.assertNotIn("Output:", out)

    def test_build_run_input_without_attachments_is_unchanged(self) -> None:
        class M:
            role = "assistant"
            content = "Plain reply, no Outputs."
            attachments = None

        out = build_run_input([M], "current?")
        self.assertNotIn("Output:", out)
        self.assertIn("Plain reply, no Outputs.", out)


if __name__ == "__main__":
    main()
