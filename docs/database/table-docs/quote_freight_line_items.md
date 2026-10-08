# `quote_freight_line_items`

## Searchable Aliases
estimated shipping, freight quotes, outbound transport fees, delivery estimates

## Description
The `quote_freight_line_items` table manages the estimated shipping and handling charges applied to a Sales Quote. Because many of the industrial components in the **Lyndom** (the current PostgreSQL ERP) catalog (such as HVAC units or engine blocks) require specialized freight, this table allows sales teams to include precise logistics costs in their customer proposals.

Upon conversion of a Quote to a Sales Order, these estimates are transitioned into the official `sales_order_freight_line_items` ledger.

## ⚙️ The Pricing & Approval Workflow
1.  **Estimation**: During quote preparation, a user adds one or more freight lines, selecting a preferred `carrier_id` and `shipping_service_type_id` (e.g., "Standard Ground" or "LTL Truck").
2.  **Logic Separation**: Freight is tracked as a separate revenue line, ensuring that the product margin calculations on the `quotes` header remain accurate and uncontaminated by logistics surcharges.
3.  **The Confirmation Gate**: The `is_confirmed` flag is used as a technical checkpoint. It ensures that a logistics manager or coordinator has specifically reviewed and greenlit the shipping estimate before it is presented to the client in a final proposal.
4.  **Conversion**: Once a quote is `SOLD`, this record provides the template for the legally binding freight charges on the resulting Sales Order.

## ⚠️ SQL-Critical Behaviors
- **Inactive Estimates**: The `is_active` flag allows for multiple freight scenarios (e.g., "Air" vs "Sea") to be proposed. The salesperson can toggle them off to remove them from the total without deleting the historical data.
- **Service Type Linkage**: By linking to the `shipping_service_types` table, the system ensures that the Quote includes the correct service level names for the customer-facing printed proposal.

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch issuing the quote. |
| quote_id | uuid | no | — | Link to the parent proposal in `quotes.id`. |
| price | numeric(12,2) | no | — | **Estimated Charge**: The dollar amount the client is quoted for this shipping service. |
| description | text | yes | — | Human-readable name of the charge (e.g., "Freight Estimate"). |
| carrier_id | uuid | yes | — | Link to `carriers.id` (e.g., FedEx, UPS). |
| shipping_service_type_id | uuid | yes | — | Link to `shipping_service_types.id` (e.g., "Ground"). |
| is_confirmed | bool | no | false | **Approval Sentinel**: If `true`, the logistics estimate has been verified. |
| is_active | bool | no | true | Global status flag. If `false`, the charge is excluded from the quote total. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| quote_id | quotes | id | cascade |
| carrier_id | carriers | id | set null |
| shipping_service_type_id | shipping_service_types | id | set null |

## Common Query Patterns
```sql
-- Find all pending quotes that are currently missing a confirmed freight estimate
SELECT q.number, q.order_total 
FROM quotes q
LEFT JOIN quote_freight_line_items f ON q.id = f.quote_id
WHERE q.status = 'PENDING' AND (f.is_confirmed = false OR f.id IS NULL);

-- List the most frequently used carriers for recent sales proposals
SELECT c.name, COUNT(f.id) 
FROM quote_freight_line_items f
JOIN carriers c ON f.carrier_id = c.id
GROUP BY c.name;
```

## Indexes
- *Relies on standard relational indexes for document generation.*
