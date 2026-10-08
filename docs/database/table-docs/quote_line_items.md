# `quote_line_items`

## Searchable Aliases
quoted parts, proposal items, bid components, sales estimation details

## Description
The `quote_line_items` table contains the granular itemization of a sales proposal. Each record represents a specific product (SKU) or service being quoted to a client, including its negotiated price, tax status, and delivery flags. 

Unlike a permanent Sales Order, the quote line item is a "Negotiable Record"—it captures the intended commercials before they are legally frozen into a contract.

## ⚙️ The Presentation & Formatting Workflow
- **Logical Sectioning**: The `group` and `sort` columns are used by the UI to organize the quote into human-readable sections (e.g., "Equipment", "Labor", "Optional Upgrades"). This allows for complex projects to be presented clearly to the client.
- **Tax & Tariff Logic**: Each line item independently tracks its `tax_rate` and `tariff_rate`, allowing for mixed orders of taxable goods and non-taxable technical services.
- **Physical Fulfillment Prep**: The `shippable` flag identifies if the item requires warehouse logistics (physical goods) or if it is an intangible service.

## ⚠️ SQL-Critical Behaviors
- **Line-Level Confirmation**: The `is_confirmed` flag acts as an item-level lock. A quote cannot be converted to a Sales Order unless all required lines are marked as confirmed by the salesperson or customer.
- **Commission Control**: If `non_commissionable = true`, the value of this line is excluded from the commission calculations on the parent `quotes` record (typically used for pass-through costs or flat fees).
- **Price Snapshots**: The table stores the `price` and `discount` at the moment of entry. This "Locks in" the offer for the client, even if the master price in the `items` catalog changes during the negotiation.

## Columns (30 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the quote. |
| quote_id | uuid | no | — | Link to the parent header in `quotes.id`. |
| group | int4 | no | — | Section ID for grouping items on the printed quote. |
| sort | int4 | no | — | Display order within the group. |
| item_store_id | uuid | no | — | Link to the internal branch SKU in `item_stores.id`. |
| item_no | text | no | — | **Denormalized SKU**: The code of the item for the printed quote. |
| item_name | text | no | — | **Denormalized Name**: The display name of the item. |
| item_description | text | no | — | Technical description or scope for the line. |
| quantity | numeric(12,2) | no | — | Number of units being proposed. |
| taxable | bool | no | — | If `true`, sales tax is applied to this line. |
| price | numeric(12,2) | no | — | **Unit Quote Price**: The price offered to the client. |
| price_label | text | yes | — | Optional custom text for the price field (e.g., "Promo Rate"). |
| tax_rate | numeric(12,2) | no | — | The tax percentage applied to this SKU. |
| tariff_rate | numeric(12,2) | no | — | The tariff/duty percentage applied. |
| discount_rate | numeric(12,2) | no | — | Percentage discount for this specific line. |
| tax_amount | numeric(12,2) | no | 0 | Calculated dollar value of tax. |
| discount_amount | numeric(12,2) | no | 0 | Calculated dollar value of the discount. |
| total_amount | numeric(12,2) | no | 0 | **Line Total**: (Qty * Price) + Tax - Discount. |
| overage | numeric(12,2) | no | — | Surcharge amount for high-margin line items. |
| tariff_amount | numeric(12,2) | no | 0 | Calculated dollar value of tariffs. |
| tariffable | bool | no | — | If `true`, tariffs are applied to this record. |
| non_commissionable | bool | no | — | If `true`, this line is excluded from rep commission totals. |
| is_active | bool | no | true | Global status flag. |
| shippable | bool | no | true | If `true`, requires physical warehouse packaging. |
| note | text | yes | — | Internal-only comments or technical specs for the line. |
| is_confirmed | bool | no | false | **Approval Sentinel**: Indicates the customer has greenlit this specific SKU. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| quote_id | quotes | id | cascade |
| item_store_id | item_stores | id | cascade |

## Common Query Patterns
```sql
-- List all items proposed for a specific project section
SELECT item_name, quantity, price 
FROM quote_line_items 
WHERE quote_id = '<uuid>' AND "group" = 1 
ORDER BY sort ASC;

-- Identify highly discounted items across all current quotes
SELECT item_no, discount_rate 
FROM quote_line_items 
WHERE discount_rate > 20 AND is_active = true;
```

## Indexes
- *Relies on standard relational indexes on `quote_id` and `item_store_id` for document generation.*
