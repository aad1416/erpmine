"""Tool-boundary tests for `analyze` (ticket 09): invoked the way the SDK does, via
on_invoke_tool with a real ToolContext, against a ReportsToolContext whose result
store is pre-seeded directly (prior art: tests/services/test_reports_agent_runner.py).

Covers: chaining by query_id with lineage carried forward, the derived result's shape
(source_query_id + notes[]), an Output built from a derived result carrying the full
transform chain in its provenance, unknown query_id, and a Transform error surfacing
as a string rather than raising.
"""

import json
from datetime import datetime, timezone

import pytest
from agents.tool_context import ToolContext

from app.services.reports_agent_runner import (
    ReportsToolContext,
    StoredResult,
    analyze,
    create_table,
)


def _ctx(**overrides):
    defaults = dict(
        feature_id=1,
        store_id="store-9",
        user_id="u-1",
        user_accesses=[],
        database_query_tool_service=None,
    )
    defaults.update(overrides)
    return ReportsToolContext(**defaults)


async def _invoke(tool, ctx, tool_name, **arguments):
    arguments_json = json.dumps(arguments)
    return await tool.on_invoke_tool(
        ToolContext(
            ctx, tool_name=tool_name, tool_call_id="call-1", tool_arguments=arguments_json
        ),
        arguments_json,
    )


async def _analyze(ctx, query_id, params):
    return await _invoke(analyze, ctx, "analyze", query_id=query_id, params=params)


async def _create_table(ctx, query_id, title):
    return await _invoke(create_table, ctx, "create_table", query_id=query_id, title=title)


def _seed(ctx, query_id, rows, sql="SELECT 1", lineage=None):
    ctx.results[query_id] = StoredResult(
        columns=list(rows[0].keys()) if rows else [],
        rows=rows,
        sql=sql,
        lineage=lineage or [],
    )
    ctx._query_counter = max(ctx._query_counter, int(query_id[1:]))


@pytest.mark.asyncio
async def test_analyze_stores_derived_result_under_next_query_id():
    ctx = _ctx()
    _seed(
        ctx,
        "q1",
        [
            {"vendor": "V1", "total": 500},
            {"vendor": "V2", "total": 400},
            {"vendor": "V3", "total": 100},
        ],
        sql="SELECT vendor, total FROM t",
    )

    result = await _analyze(
        ctx,
        "q1",
        {"transform": "top_n", "label_col": "vendor", "value_col": "total", "n": 2},
    )

    assert result["query_id"] == "q2"
    assert result["source_query_id"] == "q1"
    assert result["columns"] == ["rank", "vendor", "total", "share_pct"]
    assert result["row_count"] == 3  # top 2 + Other
    assert result["notes"] == ["1 row(s) rolled into Other"]

    derived = ctx.results["q2"]
    assert derived.sql == "SELECT vendor, total FROM t"
    assert derived.lineage == [
        {
            "transform": "top_n",
            "params": {"label_col": "vendor", "value_col": "total", "n": 2, "other": True, "ascending": False},
        }
    ]


@pytest.mark.asyncio
async def test_analyze_chains_lineage_across_two_transforms():
    ctx = _ctx()
    _seed(
        ctx,
        "q1",
        [
            {"client": "Acme", "year": 2021, "revenue": 500},
            {"client": "Acme", "year": 2022, "revenue": 100},
            {"client": "Globex", "year": 2021, "revenue": 100},
            {"client": "Globex", "year": 2022, "revenue": 500},
        ],
        sql="SELECT client, year, revenue FROM t",
    )

    trend = await _analyze(
        ctx,
        "q1",
        {
            "transform": "period_trend",
            "entity_col": "client",
            "period_col": "year",
            "value_col": "revenue",
            "direction": "down",
        },
    )
    assert trend["query_id"] == "q2"

    top = await _analyze(
        ctx, "q2", {"transform": "top_n", "label_col": "client", "value_col": "change_abs", "n": 1}
    )
    assert top["query_id"] == "q3"
    assert top["source_query_id"] == "q2"

    derived = ctx.results["q3"]
    assert [step["transform"] for step in derived.lineage] == ["period_trend", "top_n"]
    assert derived.sql == "SELECT client, year, revenue FROM t"  # root SQL carried through


@pytest.mark.asyncio
async def test_analyze_notes_are_surfaced():
    ctx = _ctx()
    _seed(ctx, "q1", [{"days_late": -2}, {"days_late": 40}, {"days_late": None}])

    result = await _analyze(
        ctx, "q1", {"transform": "bucket", "value_col": "days_late", "preset": "days_late"}
    )

    assert result["query_id"] == "q2"
    assert any("null days_late" in note for note in result["notes"])


@pytest.mark.asyncio
async def test_analyze_returns_error_string_for_unknown_query_id():
    ctx = _ctx()

    result = await _analyze(
        ctx, "q404", {"transform": "top_n", "label_col": "a", "value_col": "b"}
    )

    assert result == "Error: unknown query_id 'q404'; call query_database first."
    assert ctx.results == {}


@pytest.mark.asyncio
async def test_analyze_transform_error_is_a_string_not_an_exception():
    ctx = _ctx()
    _seed(ctx, "q1", [{"vendor": "V1", "total": "not-a-number"}])

    result = await _analyze(
        ctx, "q1", {"transform": "top_n", "label_col": "vendor", "value_col": "total"}
    )

    assert isinstance(result, str)
    assert result.startswith("Error:")
    assert "q2" not in ctx.results


@pytest.mark.asyncio
async def test_output_from_derived_result_carries_full_provenance_chain():
    ctx = _ctx()
    _seed(ctx, "q1", [{"vendor": "V1", "total": 500}, {"vendor": "V2", "total": 100}], sql="SELECT * FROM t")

    await _analyze(ctx, "q1", {"transform": "top_n", "label_col": "vendor", "value_col": "total", "n": 1})
    ack = await _create_table(ctx, "q2", "Top vendor")

    assert ack["ok"] is True
    table = ctx.attachments[0]
    assert table.provenance.sql == "SELECT * FROM t"
    assert [step.model_dump() for step in table.provenance.transforms] == [
        {
            "transform": "top_n",
            "params": {"label_col": "vendor", "value_col": "total", "n": 1, "other": True, "ascending": False},
        }
    ]
    assert table.provenance.row_count == table.row_count
    assert isinstance(table.provenance.generated_at, datetime)
    assert table.provenance.generated_at.tzinfo is not None
