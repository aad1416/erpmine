from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config.setting import settings

"""Lyndom DB repository boundary.

Why this exists:
- Keeps all Lyndom database access in one dedicated repository object.
- Provides one place to enforce read-only safeguards for LLM-generated SQL.
- Offers a stable API for services so schema/query changes stay localized.

Design strategy:
- Maintain a single repository abstraction for the whole Lyndom DB.
- Add named query methods for common business reads.
- Keep `execute_query` as a guarded fallback for dynamic read-only queries.

See `docs/lyndom-db-repository-strategy.md` for full rationale and usage.
"""


class LyndomDBRepository:
    """Single access point for Lyndom DB read/query operations."""

    def __init__(self, db_url: str, statement_timeout_ms: int | None = None):
        if statement_timeout_ms is None:
            statement_timeout_ms = settings.LYNDOM_SQL_TIMEOUT_MS
        # Server-side cap on every statement this engine runs (libpq `options`),
        # so no per-query code has to enforce it. Postgres cancels the statement
        # and the driver raises, which `execute_query` callers already handle.
        self._engine = create_engine(
            db_url,
            connect_args={"options": f"-c statement_timeout={int(statement_timeout_ms)}"},
        )

    # ------------------------------------------------------------------ #
    # Named queries — add specific methods here as needed                  #
    # ------------------------------------------------------------------ #

    def get_users(self, limit: int = 100) -> list[dict]:
        return self.execute_query("SELECT * FROM users LIMIT :limit", {"limit": limit})

    def get_stores(self, limit: int | None = None) -> list[dict]:
        if limit is not None:
            return self.execute_query("SELECT * FROM stores LIMIT :limit", {"limit": limit})
        return self.execute_query("SELECT * FROM stores")

    def get_clients(self, limit: int | None = None) -> list[dict]:
        if limit is not None:
            return self.execute_query("SELECT DISTINCT * FROM clients LIMIT :limit", {"limit": limit})
        return self.execute_query("SELECT DISTINCT * FROM clients")

    def get_store_email(self, store_id: str) -> str | None:
        rows = self.execute_query(
            "SELECT contact_info_email FROM stores WHERE id = :store_id",
            {"store_id": store_id},
        )
        return rows[0].get("contact_info_email") if rows else None

    # ------------------------------------------------------------------ #
    # Generic read-only query — used by DBQueryService / LLM-generated SQL #
    # ------------------------------------------------------------------ #

    def execute_query(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute a read-only SQL query and return rows as dicts.

        Raises ValueError for non-SELECT statements so callers can surface
        a clean error rather than letting a write slip through.
        """
        normalized = query.strip().upper().lstrip("(")
        if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
            raise ValueError("Only SELECT/WITH queries are permitted")

        with self._engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            columns = list(result.keys())
            return [dict(zip(columns, row)) for row in result.fetchall()]

    # ------------------------------------------------------------------ #
    # Schema introspection — useful for Text-to-SQL context building       #
    # ------------------------------------------------------------------ #

    def get_schema(self) -> dict[str, list[dict]]:
        """Return a map of table_name → list of column descriptors.

        Each descriptor: {"name": str, "type": str, "nullable": bool, "primary_key": bool}
        """
        inspector = inspect(self._engine)
        schema: dict[str, list[dict]] = {}

        for table_name in inspector.get_table_names():
            columns = []
            pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []))
            for col in inspector.get_columns(table_name):
                columns.append(
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                        "primary_key": col["name"] in pk_cols,
                    }
                )
            schema[table_name] = columns

        return schema
