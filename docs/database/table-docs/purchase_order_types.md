# `purchase_order_types`

## Searchable Aliases
procurement categories, po classification, order types

## Description
The `purchase_order_types` table defines the specific procurement workflows available in the system. These types distinguish between standard inventory restock, specific customer order fulfillment, and long-term vendor contracts. By categorizing Purchase Orders (POs), the system can apply specialized logic for tracking, billing, and fulfillment depending on the PO's purpose. The ERP utilizes protected, system-standard types to drive these different procurement behaviors. Examples of actual values include `SO` (Sales Order), `Service`, `Field Service`, and `Blanket`.

## ⚠️ SQL-Critical Behaviors
- **System-Default Logic**: Records where `protected = true` (e.g., `SO`, `Blanket`) are tied to internal application workflows. For instance, an `SO` type PO likely requires a link to a parent Sales Order to justify the purchase. 
- **Workflow Differentiation**: Choosing a PO Type determines which mandatory fields are required (e.g., a `Field Service` PO might require a Ticket ID).
- **Tenant Isolation**: PO Types are scoped to a `store_id`, allowing branches to enable only the procurement models relevant to their operations.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | — | PO Type name. Examples of actual values include: `SO`, `Blanket`, `Service`, `Field Service`. |
| protected | bool | no | false | If `true`, this is a system-standard type with reserved logic. |
| creator_id | uuid | no | — | The user who registered this PO type. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| purchase_orders | purchase_order_type_id | Determines the workflow rules for the specific PO. |

## Common Query Patterns
```sql
-- Find all 'Blanket' purchase orders currently open with a vendor
SELECT po.number, v.name 
FROM purchase_orders po
JOIN vendors v ON po.vendor_id = v.id
JOIN purchase_order_types pot ON po.purchase_order_type_id = pot.id
WHERE pot.name = 'Blanket' AND po.is_active = true;

-- Count procurement activity by type for a specific branch
SELECT pot.name, COUNT(po.id) 
FROM purchase_orders po
JOIN purchase_order_types pot ON po.purchase_order_type_id = pot.id
WHERE po.store_id = '<store_uuid>'
GROUP BY pot.name;
```

## Indexes
- *Uses default PK and FK constraints.*


