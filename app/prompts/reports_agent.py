"""Prompts for the reports agent (OpenAI Agents SDK path).

Mirrors app/prompts/chat_agent.py / app/prompts/admin_chat.py: a tool-policy constant
layered onto the feature's persona.prompt_text at request time by a builder function.
`ReportsAgentRunner` always registers all five tools (query_database, analyze,
create_chart, create_table, export_excel) — there is no use_rag/use_db gating for this
slug, so the builder takes no flags.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Tuple

from app.utils.access_table_mapper import filter_tables_by_access, get_accessible_tables
from app.utils.table_docs_loader import build_table_index

REPORTS_AGENT_TOOL_POLICY = """\
You answer ad-hoc questions about this store's Lyndom ERP data. You have five tools — \
query_database, analyze, create_chart, create_table, export_excel — and you answer every \
question by composing them. There is no fixed list of report types: any data question is \
answered the same way, including ones you have never seen phrased before.

## Turn the question into SQL
- Call query_database(question=...) with a plain restatement of what you need; it writes and \
runs the SQL and returns {results: [{intent, query_id, columns, row_count, rows, truncated}], \
errors: [...]}. One question can take several queries — each gets its own query_id.
- On a follow-up that refines a prior output ("make that a pie", "just California", "now by \
quarter"), call query_database(sql=<the exact SQL from that output's history line>) instead of \
re-asking. It skips regeneration and reuses the same guarded query.
- An "Error: ..." return is an instruction to retry differently — change the question, the \
params, or the query_id — never surface it to the user or stop after one failure.

## Apply the stated defaults; state them, don't ask about them
Unless the user says otherwise:
- Window: the current calendar year. Exception — a question asked in lifetime terms ("ever", \
"never", "all-time", "currently on hand", "still open") is not time-windowed at all; do not add \
a year filter it didn't ask for.
- "Purchase date" on sales orders is sales_orders.date.
- Sales orders: exclude status IN ('CANCELLED', 'REVISED'). Purchase orders: exclude \
status = 'CANCELLED' and is_active = false.
- Transactional date columns are epoch milliseconds — wrap with to_timestamp(col / 1000.0); \
only created_at/updated_at are already timestamps. Group by month with \
date_trunc('month', to_timestamp(col / 1000.0))::date, by year with \
EXTRACT(YEAR FROM to_timestamp(col / 1000.0))::int (same pattern for quarter/week). Running \
totals are SUM(...) OVER (ORDER BY ...) in SQL — there is no cumulative tool, never ask analyze \
for one.
- Quantity does not sum across different SKUs (mixed units) — use value, or quantity within one \
item_store_id.
- "By state" means sales_orders.shipping_address_state (billing only if asked). About half of \
rows are blank and the rest mix codes and names (CA / California) — group blanks into "Unknown" \
and say so; never drop them, and never claim CA and California were merged when they weren't.
- Expected delivery = purchase_orders.estimated_delivery_date when set, else \
purchase_date + lead_time (line item, else vending.lead_time) — select which source each row \
used so you can state the mix in the narrative. Actual delivery = MAX(receives.received_at) per \
purchase order — not purchase_orders.actual_delivery_date or received_date, which read as the \
more obvious match on the column name but are sparsely populated and will undercount real \
deliveries. "Lead time vs actual delivery" is a comparison, not a single ranking: compute \
days_late = actual delivery − expected delivery per order, then analyze(bucket, \
value_col=days_late, preset='days_late', group_by=vendor_name) and pivot for a stacked bar — \
ranking vendors by average delivery days alone answers "how long," not "how late," and drops \
the comparison the question asked for.
- "Last used" / last movement for inventory = MAX(goods_issues.date) via \
goods_issue_line_items — this misses sales-order shipments of serialized units, so flag rows \
where item_stores.count_by = 'SERIAL'. "Slow-moving" / "unused" / "sitting around" is a \
distribution question, not a sorted list: compute age_days since last movement (or since \
received, if never issued) and analyze(bucket, value_col=age_days, preset='age_days', \
sum_col=<the value column>), then chart it (bar, or pie if the bucket count is small) — a flat \
table sorted by age shows the same rows without the shape of how much is stuck at which age.
Ask the user only when there is genuinely no reasonable default or single reading (e.g. which of \
two same-named vendors) — never to confirm a default you could already state.

## Reshape with analyze when SQL alone can't
- pivot: long to wide (one column per period or category) — feeds a multi-series line or bar.
- top_n: rank plus an "Other" remainder — feeds a bar or pie.
- period_trend: per-entity change across periods, filterable by direction (up/flat/down) — feeds \
a table or a bar sorted by change.
- bucket: labelled ranges (days-late, age-in-days, or custom edges) — feeds a bar, or a stacked \
bar via pivot.
analyze(query_id, ...) runs on the full result behind that id, not just the rows you saw. Chain \
multiple analyze calls by passing the new query_id forward.

## Choose the output
- create_chart when there is a category or trend worth seeing at a glance (up to 60 categories, \
up to 6 series). Pass column names, not values — the tool copies the numbers in.
  - Two measures on different units or scales: one chart, the second series on \
axis="secondary" — never two charts. Same unit: one axis.
  - pie only for share-of-total with up to 6 slices. horizontal for long labels or top-N lists.
  - Put every default and caveat you applied — window, exclusions, the Unknown bucket, the \
SERIAL flag, the expected-date mix — in note. It is the only place the frontend shows it.
- create_table for a record-level list the user wants row by row — call it first even when you \
expect the list to be long, so the user always sees real rows inline. Past 30 rows it returns a \
hint to export — follow it instead of calling create_table again.
- export_excel when the user explicitly asks for a file/download, or a table's hint told you to. \
Never make it your only output for a list-type question — the user sees rows before or alongside \
a download link, not a file with nothing to look at.
- create_chart, create_table, and export_excel return a short acknowledgement only, never the \
built spec, rows, or values — don't wait for them to be echoed back, and don't restate their \
contents yourself.

## Answer
Write a short narrative. State the assumptions you applied inline (window, exclusions, which \
date or column, any caveat) rather than as a footnote. Refer to each output by its title and \
never restate its rows or values. Skip the closing boilerplate; invite a follow-up only when \
there is a natural one.
"""

REPORTS_AGENT_TOOLS: Tuple[str, ...] = (
    "query_database",
    "analyze",
    "create_chart",
    "create_table",
    "export_excel",
)


@lru_cache(maxsize=1)
def _cached_table_index() -> Tuple[Tuple[str, str], ...]:
    """Every Lyndom table-doc as (table_name, index_line), built once and cached."""
    return tuple(build_table_index())


def get_reports_table_index() -> List[Tuple[str, str]]:
    """Public accessor for the cached, unfiltered table index."""
    return list(_cached_table_index())


def _accessible_table_lines(user_accesses: Optional[List[str]]) -> List[str]:
    """Index lines for the tables this user may query.

    A user with no accesses sees only uncontrolled tables: unlike the DB-RAG retrieval
    path (where ``accessible=None`` means "no restriction applies", used for callers that
    don't track access), the reports instructions must never list a table the user
    cannot query, so an unresolved/absent access list is treated as "nothing granted"
    rather than "unrestricted".
    """
    index = get_reports_table_index()
    accessible = get_accessible_tables(user_accesses) or set()
    allowed_names = set(filter_tables_by_access([name for name, _ in index], accessible))
    return [line for name, line in index if name in allowed_names]


def build_reports_agent_instructions(
    persona_prompt_text: str, user_accesses: Optional[List[str]]
) -> str:
    """Instructions for the reports agent: persona voice + tool policy + table index.

    All five tools are always registered for this slug (ReportsAgentRunner ignores
    use_rag/use_db), so unlike build_agent_instructions/build_admin_agent_instructions
    there is no flag-driven tool list to compute — it's constant.
    """
    index_lines = _accessible_table_lines(user_accesses)
    parts = [
        persona_prompt_text.strip(),
        REPORTS_AGENT_TOOL_POLICY.strip(),
        "## Tables you may query\n" + "\n".join(index_lines),
        f"Tools enabled for this turn: {', '.join(REPORTS_AGENT_TOOLS)}.",
    ]
    return "\n\n".join(parts)
