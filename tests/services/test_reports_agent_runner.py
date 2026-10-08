"""Tool-boundary tests for the reports agent's first end-to-end path (ticket 07) plus
export_excel and the truncated-Table/Export auto-pairing (ticket 10): each
@function_tool invoked the way the SDK does, via on_invoke_tool with a real
ToolContext, against a ReportsToolContext whose query/files services are stubs
(prior art: tests/services/test_unit_rca_agent_runner.py).

Covers: query_id allocation, multi-SQL results, sql= re-run, errors never landing in
the store, create_table truncation + hint, the 8-attachment cap, unknown query_id,
export_excel's ack/ownership/filename handling, and the runner's end-of-turn
auto-export of unpaired truncated tables.
"""

import json
from dataclasses import dataclass

import pytest
from agents.tool_context import ToolContext

from app.schemas.chats import MAX_CATEGORIES
from app.services.database_query_tool_service import ExecutedQuery
from app.services.reports_agent_runner import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    ReportsToolContext,
    auto_export_unpaired_tables,
    create_chart,
    create_table,
    export_excel,
    query_database,
)


class _StubQueryService:
    """Stands in for DatabaseQueryToolService.query_structured — returns a canned
    list of ExecutedQuery per call and records the kwargs it was invoked with."""

    def __init__(self, executed_by_call):
        self._executed_by_call = list(executed_by_call)
        self.calls = []

    async def query_structured(self, **kwargs):
        self.calls.append(kwargs)
        return self._executed_by_call.pop(0)


@dataclass
class _StubFile:
    id: str
    file_name: str
    mime_type: str
    size: int
    user_id: str


class _StubFilesService:
    """Stands in for FilesService.create_from_bytes — records the kwargs it was
    invoked with and returns a fake File-like record, no disk I/O."""

    def __init__(self):
        self.calls = []
        self._next_id = 0

    def create_from_bytes(self, content, file_name, mime_type=None, user_id=None):
        self._next_id += 1
        self.calls.append(
            dict(content=content, file_name=file_name, mime_type=mime_type, user_id=user_id)
        )
        return _StubFile(
            id=f"file-{self._next_id}",
            file_name=file_name,
            mime_type=mime_type,
            size=len(content),
            user_id=user_id,
        )


def _ctx(query_service=None, files_service=None, **overrides):
    defaults = dict(
        feature_id=1,
        store_id="store-9",
        user_id="u-1",
        user_accesses=[],
        database_query_tool_service=query_service,
        files_service=files_service,
    )
    defaults.update(overrides)
    return ReportsToolContext(**defaults)


async def _invoke(tool, ctx, tool_name, **arguments):
    arguments_json = json.dumps(arguments)
    return await tool.on_invoke_tool(
        ToolContext(
            ctx,
            tool_name=tool_name,
            tool_call_id="call-1",
            tool_arguments=arguments_json,
        ),
        arguments_json,
    )


async def _query_database(ctx, question, sql=None):
    return await _invoke(query_database, ctx, "query_database", question=question, sql=sql)


async def _create_table(ctx, query_id, title):
    return await _invoke(create_table, ctx, "create_table", query_id=query_id, title=title)


async def _create_chart(ctx, **kwargs):
    return await _invoke(create_chart, ctx, "create_chart", **kwargs)


async def _export_excel(ctx, query_id, title, filename=None):
    return await _invoke(
        export_excel, ctx, "export_excel", query_id=query_id, title=title, filename=filename
    )


async def _seed(ctx, rows, sql="SELECT 1", intent="q"):
    """Puts `rows` straight into the result store as query 'q1', the way a prior
    query_database call would, without needing a stub service per test."""
    service = _StubQueryService([[_executed(rows, sql=sql, intent=intent)]])
    ctx.database_query_tool_service = service
    result = await _query_database(ctx, intent)
    return result["results"][0]["query_id"]


def _executed(rows, sql="SELECT 1", intent="Total sales"):
    return ExecutedQuery(intent=intent, sql=sql, rows=rows, error=None, audit={"sql": sql})


def _failed(error, intent="Bad query"):
    return ExecutedQuery(intent=intent, sql="SELECT bad", rows=None, error=error, audit={"error": error})


@pytest.mark.asyncio
async def test_query_database_allocates_sequential_query_ids_across_calls():
    service = _StubQueryService(
        [
            [_executed([{"a": 1}])],
            [_executed([{"a": 2}])],
        ]
    )
    ctx = _ctx(service)

    first = await _query_database(ctx, "first question")
    second = await _query_database(ctx, "second question")

    assert [r["query_id"] for r in first["results"]] == ["q1"]
    assert [r["query_id"] for r in second["results"]] == ["q2"]
    assert set(ctx.results.keys()) == {"q1", "q2"}


@pytest.mark.asyncio
async def test_one_question_can_yield_several_query_ids():
    service = _StubQueryService(
        [[_executed([{"a": 1}], intent="Sales"), _executed([{"b": 2}], intent="Returns")]]
    )
    ctx = _ctx(service)

    result = await _query_database(ctx, "sales and returns")

    assert [r["query_id"] for r in result["results"]] == ["q1", "q2"]
    assert result["errors"] == []
    assert ctx.results["q1"].rows == [{"a": 1}]
    assert ctx.results["q2"].rows == [{"b": 2}]


@pytest.mark.asyncio
async def test_failed_query_lands_in_errors_and_audit_never_in_store():
    service = _StubQueryService([[_failed("Access denied: restricted table")]])
    ctx = _ctx(service)

    result = await _query_database(ctx, "restricted question")

    assert result["results"] == []
    assert result["errors"] == [
        {"intent": "Bad query", "error": "Access denied: restricted table"}
    ]
    assert ctx.results == {}
    assert ctx.db_queries_audit == [{"error": "Access denied: restricted table"}]


@pytest.mark.asyncio
async def test_mixed_success_and_failure_only_success_gets_a_query_id():
    service = _StubQueryService(
        [[_executed([{"a": 1}], intent="Good"), _failed("boom", intent="Bad")]]
    )
    ctx = _ctx(service)

    result = await _query_database(ctx, "question")

    assert [r["query_id"] for r in result["results"]] == ["q1"]
    assert result["errors"] == [{"intent": "Bad", "error": "boom"}]


@pytest.mark.asyncio
async def test_top_level_failure_returns_plain_string_and_touches_no_audit():
    service = _StubQueryService([[ExecutedQuery(intent=None, sql="", rows=None, error="No relevant schema was found for this question.", audit={})]])
    ctx = _ctx(service)

    result = await _query_database(ctx, "unanswerable question")

    assert result == "No relevant schema was found for this question."
    assert ctx.db_queries_audit == []
    assert ctx.results == {}


@pytest.mark.asyncio
async def test_query_database_without_service_configured_returns_error_string():
    ctx = _ctx(query_service=None)

    result = await _query_database(ctx, "any question")

    assert result == "Error: database querying is not available."


@pytest.mark.asyncio
async def test_sql_rerun_forwards_sql_and_question_to_query_structured():
    service = _StubQueryService([[_executed([{"a": 1}])]])
    ctx = _ctx(service)

    await _query_database(ctx, "make that a pie", sql="SELECT a FROM t")

    assert service.calls == [
        {
            "question": "make that a pie",
            "feature_id": 1,
            "store_id": "store-9",
            "user_accesses": [],
            "sql": "SELECT a FROM t",
        }
    ]


@pytest.mark.asyncio
async def test_create_table_returns_error_for_unknown_query_id():
    ctx = _ctx()

    result = await _create_table(ctx, "q404", "Missing")

    assert result == "Error: unknown query_id 'q404'; call query_database first."
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_table_appends_attachment_with_inferred_column_types():
    service = _StubQueryService(
        [[_executed([{"vendor_name": "Acme", "order_total": 100.0}], sql="SELECT * FROM t")]]
    )
    ctx = _ctx(service)
    await _query_database(ctx, "vendor totals")

    ack = await _create_table(ctx, "q1", "Top vendors")

    assert ack["ok"] is True
    assert ack["attachment"] == 1
    assert ack["kind"] == "table"
    assert ack["row_count"] == 1
    assert ack["truncated"] is False
    assert "hint" not in ack

    assert len(ctx.attachments) == 1
    table = ctx.attachments[0]
    assert table.title == "Top vendors"
    assert table.row_count == 1
    assert table.truncated is False
    assert table.rows == [["Acme", 100.0]]
    by_key = {c.key: c for c in table.columns}
    assert by_key["vendor_name"].type == "string"
    assert by_key["vendor_name"].label == "Vendor Name"
    assert by_key["order_total"].type == "currency"
    assert by_key["order_total"].label == "Order Total"
    assert table.provenance.sql == "SELECT * FROM t"
    assert table.provenance.row_count == 1
    assert table.provenance.transforms == []


@pytest.mark.asyncio
async def test_create_table_truncates_past_30_rows_and_hints_export():
    rows = [{"n": i} for i in range(35)]
    service = _StubQueryService([[_executed(rows)]])
    ctx = _ctx(service)
    await _query_database(ctx, "big list")

    ack = await _create_table(ctx, "q1", "Big list")

    assert ack["truncated"] is True
    assert ack["rows_shown"] == 30
    assert ack["row_count"] == 35
    assert "hint" in ack and "export_excel" in ack["hint"]

    table = ctx.attachments[0]
    assert table.truncated is True
    assert table.row_count == 35
    assert len(table.rows) == 30


@pytest.mark.asyncio
async def test_create_table_errors_at_the_attachment_cap():
    rows = [{"n": 1}]
    executed_batches = [[_executed(rows)] for _ in range(MAX_ATTACHMENTS_PER_MESSAGE + 1)]
    service = _StubQueryService(executed_batches)
    ctx = _ctx(service)

    for i in range(MAX_ATTACHMENTS_PER_MESSAGE):
        await _query_database(ctx, f"q{i}")
        ack = await _create_table(ctx, f"q{i + 1}", f"Table {i}")
        assert ack["ok"] is True

    assert len(ctx.attachments) == MAX_ATTACHMENTS_PER_MESSAGE


# ---------------------------------------------------------------------------
# create_chart (ticket 08) — the five chart-bearing client examples build a
# ChartSpec equal to the chart-spec prototype's example JSON
# (prototypes/chart_spec/chart_spec_proto.py EXAMPLES), driven from fixture rows
# through the tool boundary rather than constructed directly.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_chart_sales_by_state_dual_axis():
    ctx = _ctx()
    rows = [
        {"State": "TX", "Total value": 412500, "Orders": 318},
        {"State": "CA", "Total value": 388200, "Orders": 254},
        {"State": "FL", "Total value": 201750, "Orders": 190},
        {"State": "NY", "Total value": 154300, "Orders": 121},
        {"State": "IL", "Total value": 98400, "Orders": 96},
        {"State": "OH", "Total value": 61250, "Orders": 57},
        {"State": "Other", "Total value": 143900, "Orders": 168},
    ]
    query_id = await _seed(ctx, rows)

    ack = await _create_chart(
        ctx,
        query_id=query_id,
        type="bar",
        title="Sales by state, 2025",
        x_col="State",
        series=[
            {"col": "Total value", "name": "Total value", "format": "currency", "unit": "USD", "axis": "primary"},
            {"col": "Orders", "name": "Orders", "format": "integer", "unit": "orders", "axis": "secondary"},
        ],
        y_label="Total value",
        y2_label="Orders",
        note="Sales orders dated 2025; excludes CANCELLED and REVISED. State from shipping address.",
    )

    assert ack == {
        "ok": True,
        "attachment": 1,
        "kind": "chart",
        "title": "Sales by state, 2025",
        "categories": 7,
        "series": ["Total value", "Orders"],
    }

    spec = ctx.attachments[0].spec
    assert spec.model_dump(mode="json", exclude_none=False) == {
        "type": "bar",
        "title": "Sales by state, 2025",
        "x": {"label": "State", "values": ["TX", "CA", "FL", "NY", "IL", "OH", "Other"]},
        "series": [
            {
                "name": "Total value",
                "values": [412500, 388200, 201750, 154300, 98400, 61250, 143900],
                "format": "currency",
                "unit": "USD",
                "axis": "primary",
            },
            {
                "name": "Orders",
                "values": [318, 254, 190, 121, 96, 57, 168],
                "format": "integer",
                "unit": "orders",
                "axis": "secondary",
            },
        ],
        "y_label": "Total value",
        "y2_label": "Orders",
        "stacked": False,
        "horizontal": False,
        "note": "Sales orders dated 2025; excludes CANCELLED and REVISED. State from shipping address.",
    }
    assert ctx.attachments[0].provenance.sql == "SELECT 1"
    assert ctx.attachments[0].provenance.row_count == 7


@pytest.mark.asyncio
async def test_create_chart_monthly_sales_two_years_line_with_null_gaps():
    ctx = _ctx()
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    y2024 = [81200, 76400, 90100, 95800, 102300, 99700, 88900, 91200, 104500, 110800, 97600, 84300]
    y2025 = [88700, 82100, 97300, 101200, 109800, 105400, 94100, 98600, None, None, None, None]
    rows = [
        {"Month": m, "2024": a, "2025": b} for m, a, b in zip(months, y2024, y2025)
    ]
    query_id = await _seed(ctx, rows)

    ack = await _create_chart(
        ctx,
        query_id=query_id,
        type="line",
        title="Monthly sales, 2024 vs 2025",
        x_col="Month",
        series=[
            {"col": "2024", "name": "2024", "format": "currency", "unit": "USD"},
            {"col": "2025", "name": "2025", "format": "currency", "unit": "USD"},
        ],
        y_label="Net sales",
        note="Net of tax and freight. 2025 data through August.",
    )

    assert ack["ok"] is True
    spec = ctx.attachments[0].spec
    assert spec.model_dump(mode="json") == {
        "type": "line",
        "title": "Monthly sales, 2024 vs 2025",
        "x": {"label": "Month", "values": months},
        "series": [
            {"name": "2024", "values": y2024, "format": "currency", "unit": "USD", "axis": "primary"},
            {"name": "2025", "values": y2025, "format": "currency", "unit": "USD", "axis": "primary"},
        ],
        "y_label": "Net sales",
        "y2_label": None,
        "stacked": False,
        "horizontal": False,
        "note": "Net of tax and freight. 2025 data through August.",
    }


@pytest.mark.asyncio
async def test_create_chart_top_vendors_horizontal_with_other_rollup():
    ctx = _ctx()
    vendors = [
        "Acme Industrial Supply Co.",
        "Northwind Fasteners",
        "Gulf Coast Steel & Alloys",
        "Brightline Electrical",
        "Summit Packaging",
        "Other (14 vendors)",
    ]
    values = [612400, 455900, 398250, 210700, 164300, 287650]
    rows = [{"Vendor": v, "Purchase value": val} for v, val in zip(vendors, values)]
    query_id = await _seed(ctx, rows)

    ack = await _create_chart(
        ctx,
        query_id=query_id,
        type="bar",
        title="Top 5 vendors by purchase value, last 12 months",
        x_col="Vendor",
        series=[{"col": "Purchase value", "name": "Purchase value", "format": "currency", "unit": "USD"}],
        horizontal=True,
        note="Purchase orders excluding CANCELLED and inactive.",
    )

    assert ack["ok"] is True
    spec = ctx.attachments[0].spec
    assert spec.horizontal is True
    assert spec.x.values == vendors
    assert spec.series[0].values == values


@pytest.mark.asyncio
async def test_create_chart_vendor_delay_buckets_stacked():
    ctx = _ctx()
    vendor_names = ["Acme Industrial", "Northwind", "Gulf Coast Steel", "Brightline", "Summit"]
    buckets = {
        "Early / on time": [42, 30, 18, 25, 12],
        "1–7 days late": [9, 14, 11, 4, 6],
        "8–30 days late": [3, 6, 9, 1, 2],
        "30+ days late": [0, 2, 4, 0, 1],
    }
    rows = [
        {"Vendor": vendor_names[i], **{label: buckets[label][i] for label in buckets}}
        for i in range(len(vendor_names))
    ]
    query_id = await _seed(ctx, rows)

    ack = await _create_chart(
        ctx,
        query_id=query_id,
        type="bar",
        title="Delivery vs expected lead time, by vendor",
        x_col="Vendor",
        series=[{"col": label, "name": label, "format": "integer", "unit": "POs"} for label in buckets],
        y_label="Purchase orders",
        stacked=True,
        note="Expected = purchase date + line lead time; actual = last receipt on the PO. POs with no receipt excluded.",
    )

    assert ack["ok"] is True
    spec = ctx.attachments[0].spec
    assert spec.stacked is True
    assert [s.name for s in spec.series] == list(buckets.keys())
    for label, series in zip(buckets, spec.series):
        assert series.values == buckets[label]


@pytest.mark.asyncio
async def test_create_chart_inventory_aging_pie():
    ctx = _ctx()
    ages = ["< 90 days", "90–180 days", "180–365 days", "1–2 years", "2+ years"]
    values = [184300, 96200, 71850, 43900, 28400]
    rows = [{"Age since receipt": a, "On-hand value": v} for a, v in zip(ages, values)]
    query_id = await _seed(ctx, rows)

    ack = await _create_chart(
        ctx,
        query_id=query_id,
        type="pie",
        title="On-hand inventory value by age",
        x_col="Age since receipt",
        series=[{"col": "On-hand value", "name": "On-hand value", "format": "currency", "unit": "USD"}],
        note="Age from receipt date; 'used' = issued via goods issue.",
    )

    assert ack["ok"] is True
    spec = ctx.attachments[0].spec
    assert spec.type == "pie"
    assert spec.x.values == ages
    assert spec.series[0].values == values


# ---------------------------------------------------------------------------
# create_chart — mapping problems and validator failures each return an
# "Error: ..." string and append nothing.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_chart_unknown_query_id():
    ctx = _ctx()

    result = await _create_chart(ctx, query_id="q404", type="bar", title="Nope", x_col="a", series=[{"col": "b"}])

    assert result == "Error: unknown query_id 'q404'; call query_database first."
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_unknown_x_col():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"a": 1, "b": 2}])

    result = await _create_chart(ctx, query_id=query_id, type="bar", title="T", x_col="nope", series=[{"col": "b"}])

    assert result.startswith("Error:")
    assert "nope" in result
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_unknown_series_col():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"a": 1, "b": 2}])

    result = await _create_chart(ctx, query_id=query_id, type="bar", title="T", x_col="a", series=[{"col": "nope"}])

    assert result.startswith("Error:")
    assert "nope" in result
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_non_numeric_series_column_errors():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"vendor": "Acme", "email": "a@acme.com"}, {"vendor": "Beta", "email": "b@beta.com"}])

    result = await _create_chart(
        ctx, query_id=query_id, type="bar", title="T", x_col="vendor", series=[{"col": "email"}]
    )

    assert result == "Error: series col 'email' is not numeric."
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_more_than_60_categories_errors_pointing_at_top_n():
    ctx = _ctx()
    rows = [{"customer": f"Customer {i}", "value": i} for i in range(MAX_CATEGORIES + 1)]
    query_id = await _seed(ctx, rows)

    result = await _create_chart(
        ctx, query_id=query_id, type="bar", title="T", x_col="customer", series=[{"col": "value"}]
    )

    assert result.startswith("Error:")
    assert "analyze(top_n)" in result
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_pie_with_two_series_errors():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"label": "A", "v1": 1, "v2": 2}, {"label": "B", "v1": 3, "v2": 4}])

    result = await _create_chart(
        ctx,
        query_id=query_id,
        type="pie",
        title="T",
        x_col="label",
        series=[{"col": "v1"}, {"col": "v2"}],
    )

    assert result.startswith("Error:")
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_stacked_line_errors():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"label": "A", "v": 1}, {"label": "B", "v": 2}])

    result = await _create_chart(
        ctx, query_id=query_id, type="line", title="T", x_col="label", series=[{"col": "v"}], stacked=True
    )

    assert result.startswith("Error:")
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_all_series_secondary_errors():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"label": "A", "v": 1}])

    result = await _create_chart(
        ctx,
        query_id=query_id,
        type="bar",
        title="T",
        x_col="label",
        series=[{"col": "v", "axis": "secondary"}],
    )

    assert result.startswith("Error:")
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_stacked_with_secondary_axis_errors():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"label": "A", "v1": 1, "v2": 2}])

    result = await _create_chart(
        ctx,
        query_id=query_id,
        type="bar",
        title="T",
        x_col="label",
        series=[{"col": "v1"}, {"col": "v2", "axis": "secondary"}],
        stacked=True,
    )

    assert result.startswith("Error:")
    assert "stacked" in result.lower()
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_appends_nothing_on_error_and_leaves_attachment_count_unchanged():
    ctx = _ctx()
    query_id = await _seed(ctx, [{"label": "A", "v": "not a number"}])

    await _create_chart(ctx, query_id=query_id, type="bar", title="T", x_col="label", series=[{"col": "v"}])

    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_create_chart_errors_at_the_attachment_cap():
    ctx = _ctx()
    for i in range(MAX_ATTACHMENTS_PER_MESSAGE):
        query_id = await _seed(ctx, [{"label": "A", "v": 1}], intent=f"q{i}")
        ack = await _create_chart(ctx, query_id=query_id, type="bar", title=f"Chart {i}", x_col="label", series=[{"col": "v"}])
        assert ack["ok"] is True

    query_id = await _seed(ctx, [{"label": "A", "v": 1}], intent="overflow")
    overflow = await _create_chart(
        ctx, query_id=query_id, type="bar", title="One too many", x_col="label", series=[{"col": "v"}]
    )

    assert overflow == (
        f"Error: this message already has {MAX_ATTACHMENTS_PER_MESSAGE} outputs, "
        "the max per turn — finish with what you have."
    )
    assert len(ctx.attachments) == MAX_ATTACHMENTS_PER_MESSAGE

    await _query_database(ctx, "one more")
    overflow = await _create_table(ctx, f"q{MAX_ATTACHMENTS_PER_MESSAGE + 1}", "One too many")

    assert overflow == (
        f"Error: this message already has {MAX_ATTACHMENTS_PER_MESSAGE} outputs, "
        "the max per turn — finish with what you have."
    )
    assert len(ctx.attachments) == MAX_ATTACHMENTS_PER_MESSAGE


# ---------------------------------------------------------------------------
# export_excel (ticket 10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_excel_returns_error_for_unknown_query_id():
    ctx = _ctx(files_service=_StubFilesService())

    result = await _export_excel(ctx, "q404", "Missing")

    assert result == "Error: unknown query_id 'q404'; call query_database first."
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_export_excel_without_files_service_returns_error_string():
    service = _StubQueryService([[_executed([{"a": 1}])]])
    ctx = _ctx(service, files_service=None)
    await _query_database(ctx, "q")

    result = await _export_excel(ctx, "q1", "Title")

    assert result == "Error: file export is not available."
    assert ctx.attachments == []


@pytest.mark.asyncio
async def test_export_excel_ack_shape_and_ownership():
    rows = [{"vendor_name": "Acme", "order_total": 100.0}]
    service = _StubQueryService([[_executed(rows, sql="SELECT * FROM t")]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service, user_id="u-42")
    await _query_database(ctx, "vendor totals")

    ack = await _export_excel(ctx, "q1", "Top vendors")

    assert set(ack) == {
        "ok",
        "attachment",
        "kind",
        "title",
        "filename",
        "rows_written",
        "columns",
        "size_bytes",
    }
    assert ack["ok"] is True
    assert ack["attachment"] == 1
    assert ack["kind"] == "file"
    assert ack["title"] == "Top vendors"
    assert ack["rows_written"] == 1
    assert ack["columns"] == ["vendor_name", "order_total"]

    assert len(ctx.attachments) == 1
    file_attachment = ctx.attachments[0]
    assert file_attachment.kind == "file"
    assert file_attachment.size == ack["size_bytes"]
    assert file_attachment.provenance.sql == "SELECT * FROM t"
    assert file_attachment.provenance.row_count == 1

    assert len(files_service.calls) == 1
    call = files_service.calls[0]
    assert call["user_id"] == "u-42"
    assert call["file_name"] == file_attachment.filename
    assert len(call["content"]) == ack["size_bytes"]


@pytest.mark.asyncio
async def test_export_excel_default_filename_follows_formula():
    service = _StubQueryService([[_executed([{"a": 1}])]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service, store_id="store-9")
    await _query_database(ctx, "q")

    ack = await _export_excel(ctx, "q1", "Top vendors")

    assert ack["filename"].startswith("store-9-top-vendors-")
    assert ack["filename"].endswith(".xlsx")


@pytest.mark.asyncio
async def test_export_excel_sanitises_a_model_supplied_filename():
    service = _StubQueryService([[_executed([{"a": 1}])]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service)
    await _query_database(ctx, "q")

    ack = await _export_excel(ctx, "q1", "Title", filename="../evil.txt")

    assert ack["filename"] == "evil.xlsx"


@pytest.mark.asyncio
async def test_export_excel_errors_at_the_attachment_cap():
    rows = [{"n": 1}]
    executed_batches = [[_executed(rows)] for _ in range(MAX_ATTACHMENTS_PER_MESSAGE + 1)]
    service = _StubQueryService(executed_batches)
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service)

    for i in range(MAX_ATTACHMENTS_PER_MESSAGE):
        await _query_database(ctx, f"q{i}")
        ack = await _export_excel(ctx, f"q{i + 1}", f"Export {i}")
        assert ack["ok"] is True

    await _query_database(ctx, "one more")
    overflow = await _export_excel(ctx, f"q{MAX_ATTACHMENTS_PER_MESSAGE + 1}", "One too many")

    assert overflow == (
        f"Error: this message already has {MAX_ATTACHMENTS_PER_MESSAGE} outputs, "
        "the max per turn — finish with what you have."
    )
    assert len(ctx.attachments) == MAX_ATTACHMENTS_PER_MESSAGE


# ---------------------------------------------------------------------------
# Runner-enforced truncated-Table/Export auto-pairing (ticket 10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_export_adds_a_file_for_an_unpaired_truncated_table():
    rows = [{"n": i} for i in range(35)]
    service = _StubQueryService([[_executed(rows)]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service)
    await _query_database(ctx, "big list")
    await _create_table(ctx, "q1", "Big list")

    assert len(ctx.attachments) == 1

    await auto_export_unpaired_tables(ctx)

    assert len(ctx.attachments) == 2
    file_attachment = ctx.attachments[1]
    assert file_attachment.kind == "file"
    assert file_attachment.title == "Big list"
    assert file_attachment.provenance.row_count == 35


@pytest.mark.asyncio
async def test_auto_export_is_a_noop_when_the_model_already_exported():
    rows = [{"n": i} for i in range(35)]
    service = _StubQueryService([[_executed(rows)]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service)
    await _query_database(ctx, "big list")
    await _create_table(ctx, "q1", "Big list")
    await _export_excel(ctx, "q1", "Big list")

    assert len(ctx.attachments) == 2

    await auto_export_unpaired_tables(ctx)

    assert len(ctx.attachments) == 2


@pytest.mark.asyncio
async def test_auto_export_does_not_touch_a_non_truncated_table():
    service = _StubQueryService([[_executed([{"n": 1}])]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service)
    await _query_database(ctx, "small")
    await _create_table(ctx, "q1", "Small")

    await auto_export_unpaired_tables(ctx)

    assert len(ctx.attachments) == 1


@pytest.mark.asyncio
async def test_auto_export_pairs_by_query_id_not_just_presence_of_any_export():
    rows_a = [{"n": i} for i in range(35)]
    rows_b = [{"m": i} for i in range(35)]
    service = _StubQueryService([[_executed(rows_a), _executed(rows_b)]])
    files_service = _StubFilesService()
    ctx = _ctx(service, files_service=files_service)
    await _query_database(ctx, "two big lists")
    await _create_table(ctx, "q1", "List A")
    await _create_table(ctx, "q2", "List B")
    await _export_excel(ctx, "q1", "List A")  # only q1 is paired

    await auto_export_unpaired_tables(ctx)

    file_query_pairs = {
        query_id
        for attachment, query_id in zip(ctx.attachments, ctx.attachment_query_ids)
        if attachment.kind == "file"
    }
    assert file_query_pairs == {"q1", "q2"}
    assert len(ctx.attachments) == 4
