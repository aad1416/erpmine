# `idempotency_keys`

## Searchable Aliases
request tracking, duplicate prevention, transaction safety, api keys, unique identifiers

## Description
The `idempotency_keys` table is the **Transactional Safety Guardrail** of the **Lyndom** (the current PostgreSQL ERP) system. It is a specialized technical utility used to prevent "Double Operations"—such as double-billing a customer, double-shipping an order, or creating two identical products because of a network glitch or a nervous double-click.

By recording a unique client-provided key for every mutation request, the ERP ensures that any given operation is executed **exactly once**, regardless of how many times the request is received by the server.

## ⚙️ The Idempotency Workflow
1.  **Request Generation**: A client (Web or Mobile app) generates a unique string (the `idempotency_key`) before sending a critical request (e.g., "Submit Payment").
2.  **Safety Check**: The ERP server attempts to insert this key into the `idempotency_keys` table.
3.  **Conflict Resolution**:
    - **Success**: If the insertion succeeds, the system proceeds with the operation.
    - **Failure (Unique Violation)**: If the key already exists, the system knows this request was already processed. It skips the operation and returns the cached result of the original request.
4.  **Transaction Finality**: This mechanism acts as a "Lock" that protects the database from accidental duplication during high-concurrency events.

## ⚠️ SQL-Critical Behaviors
- **Strict Uniqueness**: The `idempotency_key` column has a hard `UNIQUE` constraint. This database-level law is what creates the "Safety Lock."
- **Performance Criticality**: This table is queried on every single mutation API call. It relies on a high-speed B-tree index to ensure the safety check doesn't slow down the system.
- **Short-Term Retention**: These keys are typically cleared periodically (e.g., every 24 hours) as they are only needed to protect against rapid-fire duplicate submissions.

## Columns (2 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| idempotency_key | varchar(255) | no | — | **The Safety Key**: Unique identifier sent by the client to prevent duplicate execution. |

## Relationships
- *None. This is a standalone technical utility table.*

## Common Query Patterns
```sql
-- Verify if a specific request key has already been consumed
SELECT id FROM idempotency_keys WHERE idempotency_key = 'req_abc123';

-- Maintenance: Count the number of unique safety locks currently active
SELECT COUNT(id) FROM idempotency_keys;
```

## Indexes
- **PKEY**: `id` [BTREE]
- **idempotency_key**: `UNIQUE INDEX [BTREE]` - The primary engine for duplicate prevention.
| Column | Type | Purpose |
|--------|------|---------|
| idempotency_key | btree (unique) | Ensures that duplicate keys cannot be inserted simultaneously. |
