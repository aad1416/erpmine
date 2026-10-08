# Verify per-block store scoping on CTE-bearing SQL instead of parsing or rewriting it

`inject_store_id_filters` (`app/utils/sql_store_guard.py`) adds a missing `alias.store_id = '…'`
filter to LLM-generated SQL as a backstop. It works via regex, with one global insertion point
per query. Testing against CTE-bearing SQL (the shape the reports agent's transforms need, per
ticket 05) found this breaks silently: when two CTEs each read a different store-scoped table,
the guard can leave one CTE with no filter at all and no query error — a cross-store data leak,
not just a bug.

We considered rewriting the guard with a real SQL parser (e.g. `sqlglot`, a new dependency) so it
could inject each filter into its correct per-CTE scope, and separately considered moving
enforcement into Postgres Row-Level Security (correct regardless of SQL shape, but a distinct
infra project). We rejected both for now: parser-based rewriting is real scope-aware engineering,
and RLS is out of scope for this effort.

Instead, we verify rather than rewrite: after generation and best-effort injection, split the SQL
into its named blocks (CTEs) and the final query using the same paren/string-aware scanning
`db_schema_markdown.py` already uses for identifier validation, and refuse to execute if any block
referencing a store-scoped table lacks its own filter inside that block. This works because the
SQL generation prompt already gives the model the real `store_id` and instructs it to filter every
store-scoped table itself — the guard's job was always backstop, not primary enforcement — so a
per-block presence check catches what injection cannot safely fix. Applies to both the reports
agent's query path and the existing chat/admin/voice query path, since the underlying gap is
shared code, not something the reports agent introduces.
