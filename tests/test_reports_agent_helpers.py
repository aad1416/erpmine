"""Lightweight unit checks (stdlib only) for the reports agent's table index and
instructions builder (ticket 06: Accessible-table index and the reports agent
instructions builder)."""

import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

import tiktoken

from app.prompts.reports_agent import (
    REPORTS_AGENT_TOOL_POLICY,
    build_reports_agent_instructions,
    get_reports_table_index,
)
from app.utils.table_docs_loader import build_table_index, resolve_table_docs_dir


class TableIndexFixtureTest(TestCase):
    """build_table_index() against a small, controlled fixture directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.docs_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, text: str) -> None:
        (self.docs_dir / f"{name}.md").write_text(text, encoding="utf-8")

    def test_extracts_first_sentence_of_description(self) -> None:
        self._write(
            "widgets",
            "# `widgets`\n\n## Description\nWidgets are small parts. They come in many colors.\n"
            "\n## Columns\n| id | uuid |\n",
        )
        with patch(
            "app.utils.table_docs_loader.resolve_table_docs_dir",
            return_value=self.docs_dir,
        ):
            index = build_table_index()
        self.assertEqual(index, [("widgets", "widgets — Widgets are small parts.")])

    def test_description_spanning_multiple_lines_is_flattened(self) -> None:
        self._write(
            "gadgets",
            "# `gadgets`\n\n## Description\nGadgets are the\nfoundation of the\ncatalog. More detail here.\n"
            "\n## Columns\n",
        )
        with patch(
            "app.utils.table_docs_loader.resolve_table_docs_dir",
            return_value=self.docs_dir,
        ):
            index = build_table_index()
        self.assertEqual(
            index, [("gadgets", "gadgets — Gadgets are the foundation of the catalog.")]
        )

    def test_missing_description_section_yields_name_only_line(self) -> None:
        self._write("undocumented", "# `undocumented`\n\n## Columns\n| id | uuid |\n")
        with patch(
            "app.utils.table_docs_loader.resolve_table_docs_dir",
            return_value=self.docs_dir,
        ):
            index = build_table_index()
        self.assertEqual(index, [("undocumented", "undocumented")])

    def test_empty_description_section_yields_name_only_line(self) -> None:
        self._write("blank", "# `blank`\n\n## Description\n\n## Columns\n")
        with patch(
            "app.utils.table_docs_loader.resolve_table_docs_dir",
            return_value=self.docs_dir,
        ):
            index = build_table_index()
        self.assertEqual(index, [("blank", "blank")])

    def test_missing_docs_dir_returns_empty_list_not_raise(self) -> None:
        with patch(
            "app.utils.table_docs_loader.resolve_table_docs_dir",
            return_value=self.docs_dir / "does-not-exist",
        ):
            self.assertEqual(build_table_index(), [])

    def test_multiple_docs_sorted_by_table_name(self) -> None:
        self._write("zebra", "# `zebra`\n\n## Description\nZ table.\n")
        self._write("alpha", "# `alpha`\n\n## Description\nA table.\n")
        with patch(
            "app.utils.table_docs_loader.resolve_table_docs_dir",
            return_value=self.docs_dir,
        ):
            index = build_table_index()
        self.assertEqual([name for name, _ in index], ["alpha", "zebra"])


class TableIndexRealDocsTest(TestCase):
    """build_table_index() against the real docs/database/table-docs directory."""

    def test_row_count_matches_number_of_docs(self) -> None:
        docs_dir = resolve_table_docs_dir()
        expected = sorted(p.stem for p in docs_dir.glob("*.md"))
        index = build_table_index()
        self.assertEqual([name for name, _ in index], expected)

    def test_no_entry_is_dropped_or_raises_for_any_doc(self) -> None:
        index = build_table_index()
        for name, line in index:
            self.assertTrue(line == name or line.startswith(f"{name} — "))

    def test_full_index_stays_within_token_budget(self) -> None:
        index = build_table_index()
        full_text = "\n".join(line for _, line in index)
        enc = tiktoken.get_encoding("cl100k_base")
        token_count = len(enc.encode(full_text))
        self.assertLess(token_count, 4000, "table index exceeds the ~3k-token budget")

    def test_no_table_doc_filename_uses_camel_case(self) -> None:
        """Acceptance probe 11 (probe 8, "freight cost by carrier last quarter")
        found docs/database/table-docs/purchaseOrder_freight_line_items.md named
        after a camelCase typo instead of the real snake_case table
        (purchase_order_freight_line_items) -- load_table_docs_markdown() and the
        table index both key off the filename stem, and the SQL generator copied
        the wrong name straight into SQL that then failed at execution with
        "relation does not exist". Every real Lyndom table name is snake_case, so
        a camelCase table-doc filename is always this class of bug."""
        docs_dir = resolve_table_docs_dir()
        offenders = [p.name for p in docs_dir.glob("*.md") if p.stem != p.stem.lower()]
        self.assertEqual(offenders, [])


class ReportsAgentInstructionsTest(TestCase):
    """build_reports_agent_instructions(): persona + policy + filtered index + tools."""

    FIXTURE_INDEX = [
        ("vendors", "vendors — Vendor master records."),
        ("affected_components", "affected_components — Parts swapped during repair."),
    ]

    def test_no_accesses_sees_only_uncontrolled_tables(self) -> None:
        with patch(
            "app.prompts.reports_agent.get_reports_table_index",
            return_value=self.FIXTURE_INDEX,
        ):
            instructions = build_reports_agent_instructions("Be concise.", None)
        self.assertIn("affected_components — Parts swapped during repair.", instructions)
        self.assertNotIn("vendors — Vendor master records.", instructions)

    def test_empty_list_accesses_sees_only_uncontrolled_tables(self) -> None:
        with patch(
            "app.prompts.reports_agent.get_reports_table_index",
            return_value=self.FIXTURE_INDEX,
        ):
            instructions = build_reports_agent_instructions("Be concise.", [])
        self.assertIn("affected_components — Parts swapped during repair.", instructions)
        self.assertNotIn("vendors — Vendor master records.", instructions)

    def test_granted_access_unlocks_the_controlled_table(self) -> None:
        with patch(
            "app.prompts.reports_agent.get_reports_table_index",
            return_value=self.FIXTURE_INDEX,
        ):
            instructions = build_reports_agent_instructions(
                "Be concise.", ["VENDOR_READ_STORE_PANEL"]
            )
        self.assertIn("vendors — Vendor master records.", instructions)
        self.assertIn("affected_components — Parts swapped during repair.", instructions)

    def test_instructions_contain_persona_policy_and_tool_names(self) -> None:
        with patch(
            "app.prompts.reports_agent.get_reports_table_index",
            return_value=self.FIXTURE_INDEX,
        ):
            instructions = build_reports_agent_instructions(
                "You are the reports voice.", ["VENDOR_READ_STORE_PANEL"]
            )
        self.assertIn("You are the reports voice.", instructions)
        self.assertIn(REPORTS_AGENT_TOOL_POLICY.strip(), instructions)
        self.assertIn(
            "Tools enabled for this turn: query_database, analyze, create_chart, "
            "create_table, export_excel.",
            instructions,
        )

    def test_get_reports_table_index_is_cached_across_calls(self) -> None:
        first = get_reports_table_index()
        second = get_reports_table_index()
        self.assertEqual(first, second)


class ReportsAgentEpochUnitPolicyTest(TestCase):
    """Acceptance probe 11 found the live Lyndom DB stores transactional epoch
    columns (sales_orders.date, purchase_orders.purchase_date, receives.received_at,
    ...) in milliseconds, not seconds: to_timestamp(date) treats them as seconds
    and produces a timestamp ~58,000 years in the future, matching zero rows on
    every calendar-year/quarter/month filter. The policy must teach the
    millisecond conversion, not the wrong second-based one."""

    def test_policy_states_epoch_milliseconds_not_seconds(self) -> None:
        self.assertIn("epoch milliseconds", REPORTS_AGENT_TOOL_POLICY)
        self.assertNotIn("epoch seconds", REPORTS_AGENT_TOOL_POLICY)

    def test_policy_teaches_the_millisecond_to_timestamp_conversion(self) -> None:
        self.assertIn("to_timestamp(col / 1000.0)", REPORTS_AGENT_TOOL_POLICY)
        self.assertNotIn("to_timestamp(col);", REPORTS_AGENT_TOOL_POLICY)


class ReportsAgentTableBeforeExportPolicyTest(TestCase):
    """Acceptance probe 11 (probe 2, "customers with a 2026 purchase") found the
    model reliably skips create_table and answers a long record-level list with
    export_excel alone (3/3 live runs) -- the user gets a download link with no
    rows ever shown in the chat, missing the ticket's "Table + Export" acceptance
    shape. The policy must make create_table the first move for a list-type
    question, and rule out export_excel as a lone answer to one."""

    def test_policy_calls_out_create_table_first_even_when_long(self) -> None:
        self.assertIn("call it first even when you expect the list to be long", REPORTS_AGENT_TOOL_POLICY)

    def test_policy_forbids_export_excel_as_the_only_output_for_a_list(self) -> None:
        self.assertIn("Never make it your only output for a list-type question", REPORTS_AGENT_TOOL_POLICY)


class ReportsAgentLeadTimeComparisonPolicyTest(TestCase):
    """Acceptance probe 11 (probe 6, "vendor lead time vs actual delivery") found
    the model compute the expected/actual/delta columns in SQL but then only
    chart average actual delivery days ranked by vendor, dropping the delta --
    answering "how long" instead of the "how late" comparison the question
    asked for, and missing the ticket's "stacked delay buckets" acceptance
    shape. The policy must name days_late = actual - expected and the
    bucket(days_late)-then-pivot path explicitly, not leave it to be inferred
    by cross-referencing the analyze section."""

    def test_policy_defines_days_late_as_actual_minus_expected(self) -> None:
        self.assertIn("days_late = actual delivery", REPORTS_AGENT_TOOL_POLICY)

    def test_policy_warns_against_a_ranking_in_place_of_the_comparison(self) -> None:
        self.assertIn('answers "how long," not "how late,"', REPORTS_AGENT_TOOL_POLICY)

    def test_policy_warns_off_the_sparse_actual_delivery_date_column(self) -> None:
        """3 live runs found the model twice substitute purchase_orders.actual_delivery_date
        (or received_date) for MAX(receives.received_at) -- it reads as the more obvious
        column-name match, but is sparsely populated and produced an all-"Unknown"
        days-late chart. The policy must name and rule out the trap column directly."""
        self.assertIn("not purchase_orders.actual_delivery_date or received_date", REPORTS_AGENT_TOOL_POLICY)


class ReportsAgentSlowMovingInventoryPolicyTest(TestCase):
    """Acceptance probe 11 (probe 7, "what inventory has been sitting around
    unused") found the model answer with a flat table sorted by last-movement
    date and no chart at all -- missing the ticket's "aging pie" acceptance
    shape and the distribution the question is really asking about (how much
    is stuck at which age), mirroring the days_late gap fixed for probe 6."""

    def test_policy_calls_out_slow_moving_as_a_distribution_question(self) -> None:
        self.assertIn('"Slow-moving" / "unused" / "sitting around" is a distribution question', REPORTS_AGENT_TOOL_POLICY)

    def test_policy_points_at_the_age_days_bucket_preset(self) -> None:
        self.assertIn("preset='age_days'", REPORTS_AGENT_TOOL_POLICY)


if __name__ == "__main__":
    main()
