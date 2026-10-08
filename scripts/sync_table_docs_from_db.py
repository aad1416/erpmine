"""
Sync table-docs markdown from the live Lyndom database schema.

- Replaces ## Columns from information_schema (correct enum vs text types).
- Replaces ## Enums Used from pg_enum for enums referenced by table columns.
- Preserves Description, SQL-Critical Behaviors, and Relationships prose.

Usage:
    python scripts/sync_table_docs_from_db.py sales_orders
    python scripts/sync_table_docs_from_db.py payments sales_orders
    python scripts/sync_table_docs_from_db.py sales_orders --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from sqlalchemy import create_engine, text

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config.setting import settings

_COLUMNS_HEADER = "| Column | Type | Nullable | Default | Business Description |"
_COLUMNS_SEPARATOR = "|--------|------|----------|---------|----------------------|"

# Curated descriptions for enum columns (override generic text after sync).
ENUM_COLUMN_DESCRIPTIONS: dict[tuple[str, str], str] = {
    (
        "payments",
        "cheque_status",
    ): "**Cheque instrument lifecycle** (`cheque_status_enum`): `NOT_REGISTERED`, `REGISTERED_BY_ISSUER`, `CONFIRMED_BY_RECEIVER`, `CASHED`. Use `CASHED` for cleared/settled cheques — not `CLEARED`.",
    (
        "payments",
        "payment_type",
    ): "**Payment instrument** (`payment_type_enum`): `CASH`, `ONLINE`, `CHEQUE`.",
    (
        "sales_orders",
        "check_status",
    ): "**Customer PO cheque match** (`sales_order_check_enum`): `NOT_CHEKCED`, `MATCH`, `MISMATCH`. Compares customer cheque/PO amounts — **not** order payment or \"unpaid\" status.",
    (
        "sales_orders",
        "status",
    ): "**Lifecycle state** (`sales_order_status_enum`): e.g. `PENDING`, `IN_PROGRESS`, `SHIPPED`, `COMPLETED`, `CANCELLED`.",
    (
        "sales_orders",
        "type",
    ): "**Order class** (`sales_order_type_enum`): e.g. `SALES`, `FIELD_SERVICE`.",
}


def _normalize_pg_type(data_type: str, udt_name: str) -> str:
    if udt_name and udt_name not in ("uuid", "text", "int8", "bool", "jsonb") and (
        udt_name.endswith("_enum") or data_type == "USER-DEFINED"
    ):
        return "enum"
    lower = data_type.lower()
    if udt_name == "uuid" or "uuid" in lower:
        return "uuid"
    if "timestamp" in lower or udt_name in ("timestamptz",):
        return "timestamptz"
    if udt_name == "bool" or "boolean" in lower:
        return "bool"
    if udt_name == "int8" or "bigint" in lower:
        return "int8"
    if "numeric" in lower or "decimal" in lower:
        return "numeric(12,2)"
    if "json" in lower:
        return "jsonb"
    if "text" in lower or "varchar" in lower or "char" in lower:
        return "text"
    return udt_name or data_type


def _fetch_live_columns(engine, table_name: str) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT column_name, data_type, udt_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name
                ORDER BY ordinal_position
                """
            ),
            {"table_name": table_name},
        ).fetchall()
    return [dict(r._mapping) for r in rows]


def _fetch_enum_labels(engine, enum_name: str) -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = :enum_name
                ORDER BY e.enumsortorder
                """
            ),
            {"enum_name": enum_name},
        ).fetchall()
    return [r[0] for r in rows]


def _format_column_row(
    table_name: str,
    name: str,
    col_type: str,
    nullable: bool,
    udt_name: str,
    existing_descriptions: dict[str, str],
) -> str:
    null_str = "yes" if nullable else "no"
    default = "—"
    override = ENUM_COLUMN_DESCRIPTIONS.get((table_name, name))
    if override:
        desc = override
    else:
        desc = existing_descriptions.get(name, "")
        if not desc or desc == f"Column `{name}`.":
            if col_type == "enum" and udt_name:
                desc = f"PostgreSQL enum `{udt_name}`."
            else:
                desc = f"Column `{name}`."
    return f"| {name} | {col_type} | {null_str} | {default} | {desc} |"


def _parse_existing_descriptions(content: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    in_columns = False
    for line in content.splitlines():
        if line.strip().startswith("## Columns"):
            in_columns = False
            continue
        if line.strip() == _COLUMNS_HEADER:
            in_columns = True
            continue
        if not in_columns:
            continue
        if line.strip().startswith("|---"):
            continue
        match = re.match(r"^\|\s*([a-z_][a-z0-9_]*)\s*\|", line.strip(), re.IGNORECASE)
        if not match:
            if line.strip().startswith("## "):
                break
            continue
        col_name = match.group(1)
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) >= 5 and parts[0].lower() != "column":
            descriptions[col_name] = parts[4]
    return descriptions


def _replace_columns_section(content: str, new_table_body: str, column_count: int) -> str:
    lines = content.splitlines()
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("## Columns") and not replaced:
            out.append(f"## Columns ({column_count} Total)")
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("| Column"):
                i += 1
            out.append("")
            out.append(_COLUMNS_HEADER)
            out.append(_COLUMNS_SEPARATOR)
            out.extend(new_table_body.splitlines())
            replaced = True
            while i < len(lines):
                if lines[i].strip().startswith("## ") and not lines[i].strip().startswith(
                    "## Columns"
                ):
                    break
                if lines[i].strip().startswith("|"):
                    i += 1
                    continue
                break
            continue
        if line.strip().startswith("## Columns"):
            i += 1
            while i < len(lines):
                if lines[i].strip().startswith("## ") and not lines[i].strip().startswith(
                    "## Columns"
                ):
                    break
                if lines[i].strip().startswith("|"):
                    i += 1
                    continue
                if lines[i].strip() == "":
                    i += 1
                    continue
                break
            continue
        out.append(line)
        i += 1
    if not replaced:
        raise ValueError("Could not find ## Columns section in markdown")
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def _build_enums_section(enum_map: dict[str, list[str]]) -> str:
    if not enum_map:
        return ""
    lines = ["## Enums Used", ""]
    for enum_name in sorted(enum_map):
        labels = enum_map[enum_name]
        backtick = ", ".join(f"`{label}`" for label in labels)
        lines.append(f"### `{enum_name}`")
        lines.append(f"(Live DB values): {backtick}.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _replace_enums_section(content: str, enums_block: str) -> str:
    lines = content.splitlines()
    out: list[str] = []
    i = 0
    inserted = False
    while i < len(lines):
        if lines[i].strip() == "## Enums Used":
            i += 1
            while i < len(lines) and not (
                lines[i].strip().startswith("## ") and lines[i].strip() != "## Enums Used"
            ):
                i += 1
            if enums_block.strip():
                if out and out[-1].strip():
                    out.append("")
                out.append(enums_block.rstrip())
                out.append("")
            inserted = True
            continue
        if (
            not inserted
            and enums_block.strip()
            and lines[i].strip() == "## Relationships"
        ):
            out.append(enums_block.rstrip())
            out.append("")
            inserted = True
        out.append(lines[i])
        i += 1
    if not inserted and enums_block.strip():
        out.append("")
        out.append(enums_block.rstrip())
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def sync_table_docs(engine, table_name: str, dry_run: bool = False) -> None:
    docs_path = os.path.join(settings.DB_RAG_TABLE_DOCS_PATH, f"{table_name}.md")
    if not os.path.isfile(docs_path):
        raise FileNotFoundError(docs_path)

    live_cols = _fetch_live_columns(engine, table_name)
    if not live_cols:
        raise ValueError(f"Table '{table_name}' not found in live database")

    with open(docs_path, encoding="utf-8") as handle:
        content = handle.read()

    existing_desc = _parse_existing_descriptions(content)

    enum_map: dict[str, list[str]] = {}
    rows: list[str] = []
    for col in live_cols:
        udt = col["udt_name"] or ""
        md_type = _normalize_pg_type(col["data_type"], udt)
        if md_type == "enum" and udt and udt not in enum_map:
            labels = _fetch_enum_labels(engine, udt)
            if labels:
                enum_map[udt] = labels
        rows.append(
            _format_column_row(
                table_name,
                col["column_name"],
                md_type,
                col["is_nullable"] == "YES",
                udt,
                existing_desc,
            )
        )

    removed = set(existing_desc) - {c["column_name"] for c in live_cols}
    added = {c["column_name"] for c in live_cols} - set(existing_desc)
    if removed:
        print(f"[{table_name}] Removed columns: {', '.join(sorted(removed))}")
    if added:
        print(f"[{table_name}] Added columns: {', '.join(sorted(added))}")
    if enum_map:
        print(f"[{table_name}] Enums: {', '.join(sorted(enum_map))}")

    updated = _replace_columns_section(content, "\n".join(rows), len(rows))
    updated = _replace_enums_section(updated, _build_enums_section(enum_map))

    if dry_run:
        print(f"[{table_name}] Dry run: would update {docs_path}")
        return

    with open(docs_path, "w", encoding="utf-8") as handle:
        handle.write(updated)
    print(f"[{table_name}] Updated {docs_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync table-docs from live DB")
    parser.add_argument(
        "table_names",
        nargs="+",
        help="Table names (e.g. sales_orders payments)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not settings.lyndom_db_url:
        raise ValueError("lyndom_db_url is not configured")

    engine = create_engine(settings.lyndom_db_url)
    for table_name in args.table_names:
        sync_table_docs(engine, table_name, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
