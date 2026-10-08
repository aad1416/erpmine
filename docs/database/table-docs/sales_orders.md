# `sales_orders`

## Searchable Aliases
customer orders, sales contracts, revenue orders, outbound orders, order header, project names

## Description
The `sales_orders` (SO) table is the authoritative commercial contract for all outbound transactions within the **Lyndom** (the current PostgreSQL ERP) system. It transitions a customer's intent (from a Quote) into a formal fulfillment commitment, anchoring the inventory reservation, dispatch logistics, and final accounting invoicing.

A Sales Order acts as the single source of truth for the project's profitability, tracking real-time margins, labor costs, and commission liabilities.

## ⚙️ The Fulfillment & Invoicing Workflow
1.  **Contract Finalization**: A User or Quote-Conversion process creates an SO. The commercial terms (Prices, Discounts, Taxes) are frozen.
2.  **Logistics Planning**: The system calculates the `estimated_ship_date`. Warehouse teams begin "Staging" the inventory.
3.  **Physical Dispatch**: Once items are picked and packed, the `actual_ship_date` is set, and the status moves to `SHIPPED`.
4.  **Accounting Graduation**: Upon shipment, the system populates the `invoice_number` and `invoice_date`. The `invoice_due_date` is then calculated based on the linked `credit_terms_id`.

## ⚠️ SQL-Critical Behaviors
- **Real-Time Margin Tracking**: The system rollsup the `part_cost` and `labor_cost` to calculate the `margin_percent`. This allows managers to audit the profitability of a deal before it even leaves the dock. 
- **The "Relational" Web**: An SO may be "In relation to" a Field Service Ticket (`in_relation_to_field_service_ticket_id`) or a specific physical unit (`unit_id`), identifying it as a repair-order rather than a standard product sale.
- **Status Enum**: Fulfillment logic depends on the `status` (`sales_order_status_enum`). (Actual values include: `PENDING`, `ACKNOWLEDGED`, `IN_PROGRESS`, `COMPLETED`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `REVISED`).
- **Check Status Enum**: `check_status` (`sales_order_check_enum`) tracks whether the customer's cheque/PO amount matches the order (`NOT_CHEKCED`, `MATCH`, `MISMATCH`). Do **not** use it for "paid" or "unpaid"; there is no `UNPAID` value. For overdue invoices use `invoice_due_date`; for customer notes use the `notes` table (`owner_type` / `owner_id`).
- **Commission Settlement**: The `total_commission` and `order_total_less_total_commission` fields define the net revenue and the payout liability for the Sales Rep or Agency.

## Columns (107 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Order entry timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| number | text | no | — | **Commercial ID**: The human-readable Sales Order number (e.g., SO-8002). |
| status | enum | no | — | **Lifecycle state** (`sales_order_status_enum`): e.g. `PENDING`, `IN_PROGRESS`, `SHIPPED`, `COMPLETED`, `CANCELLED`. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns the revenue. |
| date | int8 | no | — | The official contract date (Epoch). |
| lead_time | numeric(12,2) | yes | — | Estimated days to fulfillment. |
| sales_person_id | uuid | no | — | The primary staff member credited with the sale. |
| support_sales_person_id | uuid | yes | — | A secondary staff member assisting on the order. |
| billing_address_city | text | no | — | City for customer invoicing. |
| billing_address_address | text | no | — | Full street address for invoicing. |
| billing_address_latitude | numeric(12,2) | yes | — | Geographical coordinates for tax/billing. |
| billing_address_longitude | numeric(12,2) | yes | — | Geographical coordinates for tax/billing. |
| billing_address_postal_code | text | yes | — | Invoicing ZIP/Postal code. |
| billing_address_building_number | text | yes | — | Invoicing building ID. |
| billing_address_unit | text | yes | — | Invoicing suite/room number. |
| shipping_address_city | text | no | — | City where goods will be delivered. |
| shipping_address_address | text | no | — | Full street address for delivery. |
| shipping_address_latitude | numeric(12,2) | yes | — | Geographical coordinates for logistics/delivery. |
| shipping_address_longitude | numeric(12,2) | yes | — | Geographical coordinates for logistics/delivery. |
| shipping_address_postal_code | text | yes | — | Destination ZIP/Postal code. |
| shipping_address_building_number | text | yes | — | Destination building/gate number. |
| shipping_address_unit | text | yes | — | Destination suite/unit. |
| client_id | uuid | no | — | Link to the customer in `clients.id`. |
| rep_id | uuid | yes | — | Link to the agency/rep managing the client. |
| requested_by_id | uuid | yes | — | The specific person who authorized the order. |
| requested_by_info_name | text | yes | — | Denormalized name of the requester. |
| requested_by_info_email | text | yes | — | Contact email for order notifications. |
| requested_by_info_phone | text | yes | — | Contact phone for order updates. |
| will_call | bool | no | — | If `true`, the customer will pick up at the warehouse. |
| will_call_info_name | text | yes | — | Authorized pickup person's name. |
| will_call_info_email | text | yes | — | Pickup notification email. |
| will_call_info_phone | text | yes | — | Pickup notification phone. |
| customer_po_number | text | yes | — | The ID the customer assigned to their purchase. |
| customer_po_amount | numeric(12,2) | yes | — | The dollar value authorized by the customer. |
| customer_po_received_by_id | uuid | yes | — | User who verified the customer's legal PO. |
| customer_po_received_date | int8 | yes | — | Date the customer PO document was archived. |
| creator_id | uuid | no | — | The user who registered the order. |
| credit_terms_id | uuid | yes | — | Link to `credit_terms.id` (defining the invoice due date). |
| expedite | bool | no | — | Flag for priority warehouse processing. |
| expedite_fee | numeric(12,2) | no | — | Surcharge for expedited fulfillment. |
| commission_base_amount_manual_adjustment | numeric(12,2) | no | — | Manual override of the amount used for commission. |
| regular_commission_percentage | numeric(12,2) | no | — | Net commission rate. |
| overage_commission_percentage | numeric(12,2) | no | — | High-margin commission rate. |
| commission_base_amount | numeric(12,2) | no | — | Total dollar amount subject to commission. |
| commission_label | text | no | — | Identifying label for the commission plan. |
| regular_commission | numeric(12,2) | no | — | Calculated dollar value for regular commission payout. |
| discount_amount | numeric(12,2) | no | — | Total dollar amount deducted from the order. |
| overage_commission | numeric(12,2) | no | — | Calculated dollar value for overage commission. |
| tariff_amount | numeric(12,2) | no | — | Total import duties for the order. |
| tax_amount | numeric(12,2) | no | — | Total sales tax. |
| taxable_subtotal | numeric(12,2) | no | — | Sum of all taxable line items. |
| non_taxable_subtotal | numeric(12,2) | no | — | Sum of all non-taxable services/labor. |
| freight_cost | numeric(12,2) | no | — | The shipping fee charged to the customer. |
| freight_terms | text | no | — | Terms of transport (e.g., "Prepaid", "Collect"). |
| total_overage | numeric(12,2) | no | — | Overage amount from specific line margins. |
| total_commission | numeric(12,2) | no | — | Total commission payout liability. |
| order_total | numeric(12,2) | no | — | **Grand Total**: Final revenue including tax and freight. |
| part_cost | numeric(12,2) | no | — | Total manufacturing/buying cost for all parts on this order. |
| labor_cost | numeric(12,2) | no | — | Total cost of tech labor assigned to the order. |
| total_cost | numeric(12,2) | no | — | **Full COGS**: Total cost to fulfill this deal. |
| labor_hour | numeric(12,2) | no | — | Total man-hours required for the project. |
| margin_value | numeric(12,2) | no | — | **Absolute Margin**: (Total - Costs). |
| margin_percent | numeric(12,2) | no | — | **Margin %**: The central profitability KPI. |
| part_valuation | numeric(12,2) | no | — | Total asset value of the parts at the time of order. |
| quote_id | uuid | yes | — | **Parent Link**: The quote that originated this order. |
| in_relation_to_field_service_ticket_id | uuid | yes | — | Link to a Field Service Ticket. |
| in_relation_to_sales_order_id | uuid | yes | — | Self-reference for related orders. |
| in_relation_to_unit_id | uuid | yes | — | Link to a technical asset/unit being repaired. |
| estimated_ship_date | int8 | yes | — | The ETA for the delivery. |
| request_for_sales_order_id | uuid | yes | — | Column `request_for_sales_order_id`. |
| transfered | bool | no | — | If `true`, indicates the order data has been synchronized with an external system. |
| description | text | no | — | High-level summary of the order. |
| project_name | text | yes | — | The name of the client project (e.g., "Main St. Lighting"). |
| project_location | text | yes | — | The physical site for the order fulfillment. |
| tax_rate | numeric(12,2) | no | — | The percentage tax rate applied. |
| tariff_rate | numeric(12,2) | no | — | The percentage tariff rate applied. |
| discount_rate | numeric(12,2) | no | — | The percentage discount rate applied. |
| type | enum | no | — | **Order class** (`sales_order_type_enum`): e.g. `SALES`, `FIELD_SERVICE`. |
| special_instruction | text | no | — | Column `special_instruction`. |
| original_sales_order_id | uuid | yes | — | Link to the parent order if this is a split or revision. |
| lead_time_name | text | yes | — | Human-readable lead time (e.g., "7-10 Days"). |
| lead_time_id | uuid | yes | — | Link to `leadtimes.id`. |
| freight_method | text | no | — | Logistics carrier method (e.g., "Truck Load", "LTL"). |
| order_total_less_total_commission | numeric(12,2) | no | — | Net revenue remaining after commissions. |
| margin_without_commission | numeric(12,2) | no | — | Profitability percentage excluding rep payouts. |
| actual_ship_date | int8 | yes | — | The date the goods physically left the premise. |
| check_status | enum | no | — | **Customer PO cheque match** (`sales_order_check_enum`): `NOT_CHEKCED`, `MATCH`, `MISMATCH`. Compares customer cheque/PO amounts — **not** order payment or "unpaid" status. |
| to_be_invoiced_date | int8 | yes | — | Date the order was cleared for billing. |
| invoice_date | int8 | yes | — | Date the invoice was officially generated. |
| invoice_due_date | int8 | yes | — | Date by which payment is legally required. |
| invoice_number | text | yes | — | The unique accounting ID for the transaction. |
| billing_address_state | text | no | — | Billing state/province of the customer. **Unnormalised**: ~50% blank (`''`), remainder mixes USPS codes and full names (`CA` and `California` both occur) — report blanks as `Unknown`, never merge. |
| shipping_address_state | text | no | — | Destination state/province. **Unnormalised**: ~50% blank (`''`), remainder mixes USPS codes and full names (`CA` and `California` both occur) — the default column for "sales by state"; report blanks as `Unknown`, never merge. |
| call_twenty_four_hours_before_delivery | bool | yes | — | Column `call_twenty_four_hours_before_delivery`. |
| does_customer_po_match | bool | yes | — | Whether `customer_po_amount` reconciles with the order total. |
| original_ship_date | int8 | yes | — | Epoch timestamp of the first promised ship date, kept when `ship_date` is later revised. |
| project_id | uuid | yes | — | Link to the parent project, if the order belongs to one. |
| purchase_order_id | uuid | yes | — | Link to the inter-store `purchase_orders.id` that this SO fulfils, when another store is the buyer. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |
| note | text | no | — | Column `note`. |
| sum_of_item_overrides | numeric(12,2) | no | — | Column `sum_of_item_overrides`. |
| sum_of_units_initial_valuation | numeric(12,2) | no | — | Column `sum_of_units_initial_valuation`. |
| is_active | bool | no | — | Global visibility flag. If `false`, the order is soft-deleted/hidden. |
| sum_of_job_records_tariff | numeric(12,2) | no | — | Column `sum_of_job_records_tariff`. |
| sum_of_job_records_overhead | numeric(12,2) | no | — | Column `sum_of_job_records_overhead`. |

## Enums Used

### `sales_order_check_enum`
(Live DB values): `NEWLY_CREATED`, `NOT_CHEKCED`, `MATCH`, `MISMATCH`.

### `sales_order_status_enum`
(Live DB values): `PENDING`, `ACKNOWLEDGED`, `IN_PROGRESS`, `PARTIALLY_SHIPPED`, `PARTIALLY_DELIVERED`, `DELIVERED`, `SHIPPED`, `CANCELLED`, `REVISED`, `COMPLETED`.

### `sales_order_type_enum`
(Live DB values): `SALES`, `FIELD_SERVICE`.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| client_id | clients | id | cascade |
| quote_id | quotes | id | set null |
| credit_terms_id | credit_terms | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| sales_order_line_items | sales_order_id | The specific SKU itemization of the contract. |
| shipments | sales_order_id | Logistics vouchers for shipping the order components. |
| returns | sales_order_id | Return/RMA vouchers linked to this order. |
| notes | owner_id | Customer/staff notes when `owner_type` links to this order (use `notes.note` for free-text instructions). |

## Common Query Patterns
```sql
-- Find all Shipped orders with an outstanding balance
SELECT number, order_total, (order_total - total_cost) as profit
FROM sales_orders 
WHERE status = 'SHIPPED';

-- List all orders requiring delivery call 24 hours in advance
SELECT number, shipping_address_city, requested_by_info_phone 
FROM sales_orders 
WHERE call_twenty_four_hours_before_delivery = true AND status != 'DELIVERED';
```

## Indexes
- *Includes indexes on `check_status` and `id` for rapid commercial auditing.*
