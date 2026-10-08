# `mikro_orm_migrations`

## Searchable Aliases
database updates, schema changes, migration scripts, system versioning

## Description
The `mikro_orm_migrations` table is the **Technical Version Control Ledger** of the **Lyndom** (the current PostgreSQL ERP) system. It is managed by the application's Object-Relational Mapper (MikroORM) to track the history of changes made to the database schema (tables, columns, indexes, and constraints).

This is a purely internal system table. It ensures that the database structure remains in sync with the application code, and provides a chronological record of every technical "Evolution" the database has undergone since its creation.

## ⚙️ The Schema Evolution Workflow
1.  **Code Change**: A developer modifies the database structure in the application code (e.g., adding a new "Warranty" table).
2.  **Migration Creation**: The ORM generates a migration file—a technical script (e.g., `Migration20260420.ts`) that contains the SQL needed to create that table.
3.  **Deployment**: When the code is deployed, the system checks this table to see which migrations have already been run.
4.  **Execution & Recording**: If a migration is new, it is executed against the database, and a record is added to this table to mark it as `COMPLETED`.

## ⚠️ SQL-Critical Behaviors
- **System-Critical Authority**: This table MUST NOT be modified manually. If a record is deleted, the system may attempt to re-run an old migration (e.g., trying to create a table that already exists), leading to a crash.
- **Synchronicity Guardrail**: By checking this table on startup, the ERP ensures that developers and production servers are always working on the same "Database Version."
- **Audit Trail**: The `executed_at` timestamp provides the definitive answer to the question: "When was this feature added to the database?"

## Columns (3 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | int4 | no | — | Auto-incrementing primary key. |
| name | varchar(255) | yes | — | **Technical Version Name**: The filename of the migration script. |
| executed_at | timestamptz | no | `now()` | **Migration Timestamp**: The exact moment the schema update was applied. |

## Relationships
- *None. This is an internal system-level utility table owned by the ORM.*

## Common Query Patterns
```sql
-- List the 10 most recent database structural changes
SELECT name, executed_at 
FROM mikro_orm_migrations 
ORDER BY id DESC 
LIMIT 10;

-- Verify if the database is up to date with the latest deployment
SELECT MAX(name) FROM mikro_orm_migrations;
```

## Indexes
- **PKEY**: `id` [BTREE]
