"""Agents SDK wrapper for the reports agent: dispatch, a report-specific
`query_database`, `analyze` (ticket 09), `create_table`, `create_chart` (ticket 08),
and `export_excel` plus the truncated-Table/Export auto-pairing (ticket 10).

Mirrors `ChatAgentRunner` / `UnitRCAAgentRunner` (sibling-runner precedent): a per-turn
tool context dataclass plus a thin `Runner.run` wrapper, always registering the same
five tools and ignoring `use_rag`/`use_db` (map decision D2/D8).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import pandas as pd
from agents import Agent, RunContextWrapper, Runner, function_tool
from pydantic import BaseModel, ValidationError

from app.prompts.reports_agent import build_reports_agent_instructions
from app.schemas.chats import (
    MAX_CATEGORIES,
    MAX_SERIES,
    Attachment,
    ChartAttachment,
    ChartSpec,
    FileAttachment,
    OutputProvenance,
    TableAttachment,
    TableColumn,
    TransformStep,
)
from app.utils.column_typing import humanize_column_label, infer_column_type
from app.utils.report_transforms import AnalyzeParams
from app.utils.report_transforms import run as run_transform
from app.utils.xlsx_export import (
    XLSX_MIME_TYPE,
    build_report_workbook,
    default_export_filename,
    sanitize_export_filename,
)

if TYPE_CHECKING:
    from app.services.database_query_tool_service import DatabaseQueryToolService
    from app.services.files import FilesService

logger = logging.getLogger(__name__)

# Fixed per the spec's limits table (issues/07-limits-and-guardrails.md).
MAX_TURNS = 20
MAX_ATTACHMENTS_PER_MESSAGE = 8
INLINE_ROW_LIMIT = 30

_ATTACHMENT_CAP_ERROR = (
    f"Error: this message already has {MAX_ATTACHMENTS_PER_MESSAGE} outputs, "
    "the max per turn — finish with what you have."
)


@dataclass
class StoredResult:
    """One `query_database`/`analyze` result, keyed by `query_id`. Holds the *full*
    rows so output tools can copy from it without the model re-pasting values."""

    columns: List[str]
    rows: List[dict]
    sql: str
    lineage: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportsToolContext:
    """Per-turn tool context (dataclass mirrors `ChatToolContext`). Lives for one
    turn: created with the run, dropped when it returns."""

    feature_id: int
    store_id: Optional[str]
    user_id: str
    user_accesses: List[str]
    database_query_tool_service: Optional["DatabaseQueryToolService"]
    files_service: Optional["FilesService"] = None

    results: Dict[str, StoredResult] = field(default_factory=dict)
    attachments: List[Attachment] = field(default_factory=list)
    # Parallel to `attachments` — the `query_id` each Output was built from, kept
    # off the persisted schema (D5 has no such field) so the runner can enforce
    # the truncated-Table/Export pairing (issues/07) without touching it.
    attachment_query_ids: List[Optional[str]] = field(default_factory=list)
    db_queries_audit: List[dict] = field(default_factory=list)

    _query_counter: int = field(default=0, repr=False)

    def next_query_id(self) -> str:
        self._query_counter += 1
        return f"q{self._query_counter}"

    def record_attachment(self, attachment: Attachment, query_id: Optional[str] = None) -> int:
        """Appends an Output and its source `query_id`, returning its 1-based
        `attachment` position for the tool's ack."""
        self.attachments.append(attachment)
        self.attachment_query_ids.append(query_id)
        return len(self.attachments)


def _json_safe(value: Any) -> Any:
    """Rows must be JSON primitives with dates as ISO strings (D5)."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _attachment_cap_error(ctx: ReportsToolContext) -> Optional[str]:
    if len(ctx.attachments) >= MAX_ATTACHMENTS_PER_MESSAGE:
        return _ATTACHMENT_CAP_ERROR
    return None


def _row_columns(rows: List[dict]) -> List[str]:
    return list(rows[0].keys()) if rows else []


@function_tool
async def query_database(
    ctx: RunContextWrapper[ReportsToolContext],
    question: str,
    sql: Optional[str] = None,
) -> Union[dict, str]:
    """Write and run guarded SQL against this store's Lyndom ERP data. One question may
    take several SQLs; each gets its own query_id you pass to analyze/create_table/
    create_chart/export_excel. On a follow-up that refines a prior output, pass sql=
    with the exact SQL from that output's history line instead of restating the
    question — it skips regeneration and reuses the same guarded query.

    question — plain restatement of what you need (also the audit label when sql= is given).
    sql — optional pre-vetted SQL to re-run verbatim through the same guards.
    """
    ctx_obj = ctx.context
    if not ctx_obj.database_query_tool_service:
        return "Error: database querying is not available."

    executed = await ctx_obj.database_query_tool_service.query_structured(
        question=question,
        feature_id=ctx_obj.feature_id,
        store_id=ctx_obj.store_id,
        user_accesses=ctx_obj.user_accesses,
        sql=sql,
    )

    if len(executed) == 1 and executed[0].intent is None:
        # Tool-level failure (service disabled/unconfigured, no schema, empty question) —
        # nothing to audit, no SQL was attempted.
        return executed[0].error or "Error: the database tool failed."

    results: List[dict] = []
    errors: List[dict] = []
    for eq in executed:
        ctx_obj.db_queries_audit.append(eq.audit)
        if eq.error is not None:
            errors.append({"intent": eq.intent, "error": eq.error})
            continue

        query_id = ctx_obj.next_query_id()
        rows = eq.rows or []
        columns = _row_columns(rows)
        ctx_obj.results[query_id] = StoredResult(columns=columns, rows=rows, sql=eq.sql)

        preview = rows[:INLINE_ROW_LIMIT]
        results.append(
            {
                "intent": eq.intent,
                "query_id": query_id,
                "columns": columns,
                "row_count": len(rows),
                "rows": [[_json_safe(r.get(c)) for c in columns] for r in preview],
                "truncated": len(rows) > INLINE_ROW_LIMIT,
            }
        )

    return {"results": results, "errors": errors}


@function_tool
async def analyze(
    ctx: RunContextWrapper[ReportsToolContext],
    query_id: str,
    params: AnalyzeParams,
) -> Union[dict, str]:
    """Reshape a query_database/analyze result with a deterministic transform (pivot,
    top_n, period_trend, bucket). Runs on the full stored rows, not the preview, and
    yields a new query_id you pass to the next analyze/create_table/create_chart/
    export_excel call.

    query_id — id of a prior query_database/analyze result to reshape.
    params — the transform to run and its parameters.
    """
    ctx_obj = ctx.context
    stored = ctx_obj.results.get(query_id)
    if stored is None:
        return f"Error: unknown query_id '{query_id}'; call query_database first."

    try:
        df = pd.DataFrame(stored.rows, columns=stored.columns)
        result = run_transform(df, params)
    except Exception:
        logger.exception("analyze transform '%s' failed unexpectedly", params.transform)
        return "Error: the transform failed unexpectedly; try different columns or parameters."

    if isinstance(result, str):
        return result

    step = TransformStep(
        transform=params.transform, params=params.model_dump(exclude={"transform"})
    )
    new_query_id = ctx_obj.next_query_id()
    ctx_obj.results[new_query_id] = StoredResult(
        columns=result.columns,
        rows=result.rows,
        sql=stored.sql,
        lineage=[*stored.lineage, step.model_dump()],
    )

    preview = result.rows[:INLINE_ROW_LIMIT]
    return {
        "intent": None,
        "query_id": new_query_id,
        "source_query_id": query_id,
        "columns": result.columns,
        "row_count": len(result.rows),
        "rows": [[_json_safe(r.get(c)) for c in result.columns] for r in preview],
        "truncated": len(result.rows) > INLINE_ROW_LIMIT,
        "notes": result.notes,
    }


class ChartSeriesInput(BaseModel):
    col: str
    name: Optional[str] = None
    format: Optional[str] = None
    unit: Optional[str] = None
    axis: Optional[str] = None


def _chart_series_values(rows: List[dict], col: str) -> Optional[List[Optional[float]]]:
    """Numbers for one series column, aligned to `rows`; None = null cell. Returns
    None (the sentinel, not a list) if any non-null cell isn't numeric."""
    values: List[Optional[float]] = []
    for row in rows:
        cell = row.get(col)
        if cell is None:
            values.append(None)
            continue
        if isinstance(cell, bool) or not isinstance(cell, (int, float, Decimal)):
            return None
        values.append(float(cell))
    return values


def _chart_validation_error(exc: ValidationError) -> str:
    msg = exc.errors()[0]["msg"]
    prefix = "Value error, "
    if msg.startswith(prefix):
        msg = msg[len(prefix) :]
    return f"Error: {msg}"


@function_tool
async def create_chart(
    ctx: RunContextWrapper[ReportsToolContext],
    query_id: str,
    type: str,
    title: str,
    x_col: str,
    series: List[ChartSeriesInput],
    y_label: Optional[str] = None,
    y2_label: Optional[str] = None,
    stacked: bool = False,
    horizontal: bool = False,
    note: Optional[str] = None,
) -> Union[dict, str]:
    """Build a chart (bar/line/pie) from a query_database/analyze result's columns.
    Copies the numbers server-side from the stored rows — pass column names, never
    values.

    query_id — id from a prior query_database/analyze call.
    x_col — column supplying the categorical x axis (at most 60 distinct rows; use
        analyze(top_n) first to shrink a wider result).
    series — 1-6 numeric columns to plot; col is required, name/format/unit/axis are
        optional (name defaults to col, axis defaults to "primary").
    """
    ctx_obj = ctx.context
    cap_error = _attachment_cap_error(ctx_obj)
    if cap_error:
        return cap_error

    stored = ctx_obj.results.get(query_id)
    if stored is None:
        return f"Error: unknown query_id '{query_id}'; call query_database first."

    if x_col not in stored.columns:
        return f"Error: x_col '{x_col}' not in columns {stored.columns}."

    if not stored.rows:
        return "Error: result has no rows."

    if len(stored.rows) > MAX_CATEGORIES:
        return (
            f"Error: {len(stored.rows)} categories exceed the chart cap of "
            f"{MAX_CATEGORIES} — reduce with analyze(top_n) or use create_table / export_excel."
        )

    if not series:
        return f"Error: series must have 1..{MAX_SERIES} entries."

    categories = [
        "" if row.get(x_col) is None else str(row.get(x_col)) for row in stored.rows
    ]

    built_series: List[Dict[str, Any]] = []
    for s in series:
        if s.col not in stored.columns:
            return f"Error: series col '{s.col}' not in columns {stored.columns}."
        values = _chart_series_values(stored.rows, s.col)
        if values is None:
            return f"Error: series col '{s.col}' is not numeric."
        built_series.append(
            {
                "name": s.name or s.col,
                "values": values,
                "format": s.format or "number",
                "unit": s.unit,
                "axis": s.axis or "primary",
            }
        )

    try:
        spec = ChartSpec.model_validate(
            {
                "type": type,
                "title": title,
                "x": {"label": x_col, "values": categories},
                "series": built_series,
                "y_label": y_label,
                "y2_label": y2_label,
                "stacked": stacked,
                "horizontal": horizontal,
                "note": note,
            }
        )
    except ValidationError as exc:
        return _chart_validation_error(exc)

    attachment = ChartAttachment(
        kind="chart",
        title=title,
        spec=spec,
        provenance=OutputProvenance(
            sql=stored.sql,
            transforms=stored.lineage,
            row_count=len(stored.rows),
            generated_at=datetime.now(timezone.utc),
        ),
    )
    ctx_obj.attachments.append(attachment)
    position = len(ctx_obj.attachments)

    return {
        "ok": True,
        "attachment": position,
        "kind": "chart",
        "title": title,
        "categories": len(spec.x.values),
        "series": [s.name for s in spec.series],
    }


@function_tool
async def create_table(
    ctx: RunContextWrapper[ReportsToolContext],
    query_id: str,
    title: str,
) -> Union[dict, str]:
    """Append a Table output from a query_database/analyze result. Shows up to 30 rows
    inline; past that it returns a hint to call export_excel for the full data.

    query_id — id from a prior query_database/analyze call.
    title — short title shown to the user; the narrative should refer back to it.
    """
    ctx_obj = ctx.context
    cap_error = _attachment_cap_error(ctx_obj)
    if cap_error:
        return cap_error

    stored = ctx_obj.results.get(query_id)
    if stored is None:
        return f"Error: unknown query_id '{query_id}'; call query_database first."

    row_count = len(stored.rows)
    shown = stored.rows[:INLINE_ROW_LIMIT]
    truncated = row_count > INLINE_ROW_LIMIT

    columns = [
        TableColumn(
            key=col,
            label=humanize_column_label(col),
            type=infer_column_type(col, (r.get(col) for r in stored.rows)),
        )
        for col in stored.columns
    ]
    rows = [[_json_safe(r.get(col)) for col in stored.columns] for r in shown]

    attachment = TableAttachment(
        kind="table",
        title=title,
        columns=columns,
        rows=rows,
        row_count=row_count,
        truncated=truncated,
        provenance=OutputProvenance(
            sql=stored.sql,
            transforms=stored.lineage,
            row_count=row_count,
            generated_at=datetime.now(timezone.utc),
        ),
    )
    position = ctx_obj.record_attachment(attachment, query_id=query_id)

    ack: Dict[str, Any] = {
        "ok": True,
        "attachment": position,
        "kind": "table",
        "title": title,
        "rows_shown": len(shown),
        "row_count": row_count,
        "truncated": truncated,
    }
    if truncated:
        ack["hint"] = (
            f'Table "{title}" shows {len(shown)} of {row_count} rows — call '
            f'export_excel(query_id="{query_id}", title="{title}") for the full set.'
        )
    return ack


async def _export_excel_impl(
    ctx_obj: ReportsToolContext,
    query_id: str,
    title: str,
    filename: Optional[str] = None,
) -> Union[dict, str]:
    """Shared by the `export_excel` tool and the runner's end-of-turn auto-export
    (issues/07) — the ack/side-effects can't assume a model-initiated call."""
    cap_error = _attachment_cap_error(ctx_obj)
    if cap_error:
        return cap_error

    stored = ctx_obj.results.get(query_id)
    if stored is None:
        return f"Error: unknown query_id '{query_id}'; call query_database first."

    if ctx_obj.files_service is None:
        return "Error: file export is not available."

    generated_at = datetime.now(timezone.utc)
    columns = [
        TableColumn(
            key=col,
            label=humanize_column_label(col),
            type=infer_column_type(col, (r.get(col) for r in stored.rows)),
        )
        for col in stored.columns
    ]
    provenance = OutputProvenance(
        sql=stored.sql,
        transforms=stored.lineage,
        row_count=len(stored.rows),
        generated_at=generated_at,
    )

    workbook_bytes = build_report_workbook(columns=columns, rows=stored.rows, provenance=provenance)

    resolved_filename = (
        sanitize_export_filename(filename)
        if filename
        else default_export_filename(ctx_obj.store_id, title, generated_at)
    )

    file = ctx_obj.files_service.create_from_bytes(
        content=workbook_bytes,
        file_name=resolved_filename,
        mime_type=XLSX_MIME_TYPE,
        user_id=ctx_obj.user_id,
    )

    attachment = FileAttachment(
        kind="file",
        title=title,
        file_id=file.id,
        filename=file.file_name,
        mime_type=file.mime_type,
        size=file.size,
        provenance=provenance,
    )
    position = ctx_obj.record_attachment(attachment, query_id=query_id)

    return {
        "ok": True,
        "attachment": position,
        "kind": "file",
        "title": title,
        "filename": file.file_name,
        "rows_written": len(stored.rows),
        "columns": stored.columns,
        "size_bytes": file.size,
    }


@function_tool
async def export_excel(
    ctx: RunContextWrapper[ReportsToolContext],
    query_id: str,
    title: str,
    filename: Optional[str] = None,
) -> Union[dict, str]:
    """Write a query_database/analyze result to a downloadable .xlsx file: a `Data`
    sheet (bold frozen header, autofilter, sized columns, per-column currency/date/
    number formats) and a `Details` sheet with the SQL and transforms that produced
    it.

    query_id — id from a prior query_database/analyze call.
    title — short title shown to the user.
    filename — optional; a name you supply is sanitised and always ends in .xlsx.
    """
    return await _export_excel_impl(ctx.context, query_id, title, filename)


async def auto_export_unpaired_tables(ctx: ReportsToolContext) -> None:
    """Runner-enforced pairing (issues/07): at end of turn, any truncated Table
    with no Export sharing its query_id gets one auto-exported and appended, even
    if the model ignored create_table's hint."""
    exported_query_ids = {
        query_id
        for attachment, query_id in zip(ctx.attachments, ctx.attachment_query_ids)
        if isinstance(attachment, FileAttachment) and query_id is not None
    }
    pending = [
        (attachment, query_id)
        for attachment, query_id in zip(ctx.attachments, ctx.attachment_query_ids)
        if isinstance(attachment, TableAttachment)
        and attachment.truncated
        and query_id is not None
        and query_id not in exported_query_ids
    ]
    for table, query_id in pending:
        result = await _export_excel_impl(ctx, query_id, table.title)
        if not isinstance(result, dict):
            logger.warning(
                "Auto-export failed for query_id=%s title=%r: %s", query_id, table.title, result
            )


REPORTS_AGENT_TOOLS = (query_database, analyze, create_chart, create_table, export_excel)


class ReportsAgentRunner:
    """Runs the reports agent loop; always registers all five tools and ignores
    use_rag/use_db (there is no flag-driven tool list for this slug)."""

    async def run(
        self,
        *,
        persona_prompt_text: str,
        model_name: str,
        run_input: str,
        ctx: ReportsToolContext,
    ) -> tuple[str, List[Attachment], List[dict]]:
        instructions = build_reports_agent_instructions(persona_prompt_text, ctx.user_accesses)

        agent = Agent(
            name="reports_agent",
            instructions=instructions,
            model=model_name,
            tools=list(REPORTS_AGENT_TOOLS),
        )

        result = await Runner.run(agent, run_input, context=ctx, max_turns=MAX_TURNS)
        raw_out = result.final_output

        await auto_export_unpaired_tables(ctx)

        answer = raw_out if isinstance(raw_out, str) else str(raw_out)
        return answer, ctx.attachments, ctx.db_queries_audit
