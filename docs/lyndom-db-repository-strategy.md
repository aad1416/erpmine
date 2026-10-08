# Lyndom DB Repository Strategy

## Why we connect to Lyndom DB

The application connects to Lyndom DB to serve operational and analytical
read use-cases (for example: users, stores, clients, and schema-aware query
workflows). This data is a core source for features that require direct SQL
read access and schema introspection.

## Why we use a single repository for the whole Lyndom DB

Our strategy is to keep **one repository boundary** for the whole Lyndom DB:
`LyndomDBRepository`.

This is intentional for the following reasons:

- **Single responsibility boundary**: all Lyndom DB access logic lives in one
  place instead of being scattered across services.
- **Consistent safety controls**: read-only guardrails are centralized
  (`SELECT`/`WITH` only), especially important when SQL can be generated
  dynamically.
- **Lower maintenance cost**: connection setup, query execution, and schema
  inspection are implemented once and reused everywhere.
- **Stable service API**: service layer code depends on repository methods, not
  raw SQL connection details.
- **Easier evolution**: when table names, query patterns, or DB behavior
  changes, updates stay localized to one module.

## How this is implemented

Implementation lives in `app/repositories/lyndom_db.py` and includes:

- Named query methods for common reads (for example `get_users`,
  `get_stores`, `get_clients`).
- A generic `execute_query(...)` method for read-only SQL execution.
- `get_schema()` for table/column introspection used by text-to-SQL context.

## Usage guidance

- Keep business workflows in services/routes; keep SQL access concerns in the
  repository.
- Add new Lyndom DB read methods to `LyndomDBRepository` instead of creating
  additional Lyndom-specific repositories.
- Preserve the read-only policy in shared query execution paths.

## Future extension pattern

When new Lyndom DB capabilities are needed:

1. Add a named method to `LyndomDBRepository` when the query is reusable.
2. Use `execute_query(...)` only for controlled dynamic reads.
3. Keep write operations isolated and explicitly designed (if introduced in the
   future), rather than mixed into the current read-focused repository.
