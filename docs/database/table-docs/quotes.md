# `quotes`

## Searchable Aliases
sales proposals, bids, estimates, customer quotes, pricing offers, contract drafts

## Description
The `quotes` table stores the formal technical and commercial proposals sent to prospective or existing **Clients**. In the **Lyndom** (the current PostgreSQL ERP) system, a quote is a non-binding preliminary record that defines the items, quantities, project details (e.g., HVAC or Electrical specs), and estimated pricing.

It serves as the negotiation hub of the Sales module, tracking the evolution of a proposal through revisions until it is either **Expired** (Quote lost) or **Sold** (Converted to a legally binding Sales Order).

## ⚙️ The Quote-to-Order Workflow
1.  **Preparation**: A salesperson creates a quote in `NEW` status, defining the `project_name` and technical scope.
2.  **Negotiation**: The quote may be updated multiple times (`status = REVISED`). The system preserves the logic via `original_quote_id`.
3.  **Confirmation**: Before conversion, the `confirm_info_...` columns track the customer's verification of the billing/shipping profile and the total price.
4.  **Conversion**: Once the customer signs, the status moves to `SOLD`, and a corresponding record is automatically generated in the `sales_orders` table, linked via `sales_order_id`.

## ⚠️ SQL-Critical Behaviors
- **Commission Intelligence**: The table tracks estimated Earnings (`total_commission`) and Overage percentages during the quoting phase, allowing for immediate margin analysis by sales management.
- **Address Finalization**: Like Sales Orders, the quote contains full billing and shipping profiles. These are validated during the "Confirmation" gate mentioned above.
- **Lifecycle Enums**: Business logic depends on the `status`. (Actual values include: `NEW`, `PENDING`, `REVISED`, `EXPIRED`, `SOLD`).
- **Will-Call & Freight**: The `will_call` flag and `freight_cost` estimate define the initial logistics plan for the project.

## Columns (93 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| number | text | no | — | **Commercial ID**: The human-readable quote number (e.g., Q-5001). |
| status | enum | no | — | **Lifecycle State**: (e.g., `PENDING`, `EXPIRED`, `SOLD`). |
| store_id | uuid | no | — | **Tenant ID**: The branch issuing the proposal. |
| original_quote_id | uuid | yes | — | Self-reference to the first iteration of the quote if revised. |
| entry_date | int8 | no | — | Date the quote was registered (Epoch). |
| expire_date | int8 | no | — | Date the pricing/availability guarantee ends (Epoch). |
| lead_time | numeric(12,2) | yes | — | The total estimated days for project fulfillment. |
| sales_person_id | uuid | yes | — | The primary staff member responsible for the account. |
| support_sales_person_id | uuid | yes | — | A secondary staff member assisting on the project. |
| billing_address_city | text | no | — | City for customer invoicing. |
| billing_address_address | text | no | — | Full street address for invoicing. |
| billing_address_latitude | numeric(12,2) | yes | — | Coordinates for tax/map logic. |
| billing_address_longitude | numeric(12,2) | yes | — | Coordinates for tax/map logic. |
| billing_address_postal_code | text | yes | — | ZIP/Postal code for the billing entity. |
| billing_address_building_number | text | yes | — | Building ID for the billing entity. |
| billing_address_unit | text | yes | — | Suite/Unit for the billing entity. |
| shipping_address_city | text | no | — | Destination city for the products. |
| shipping_address_address | text | no | — | Full street address for project delivery. |
| shipping_address_latitude | numeric(12,2) | yes | — | Coordinates for logistics/delivery logic. |
| shipping_address_longitude | numeric(12,2) | yes | — | Coordinates for logistics/delivery logic. |
| shipping_address_postal_code | text | yes | — | Destination ZIP/Postal code. |
| shipping_address_building_number | text | yes | — | Destination building/gate number. |
| shipping_address_unit | text | yes | — | Destination suite/room number. |
| client_id | uuid | no | — | Link to `clients.id` (Customer or Agency). |
| rep_id | uuid | yes | — | Link to the Sales Representative managing the deal. |
| requested_by_id | uuid | yes | — | The specific person who requested the quote. |
| requested_by_info_name | text | yes | — | Denormalized name of the requesting individual. |
| requested_by_info_email | text | yes | — | Contact email for the proposal delivery. |
| requested_by_info_phone | text | yes | — | Contact phone for the proposal. |
| will_call | bool | no | — | If `true`, the customer will pick up at the warehouse. |
| will_call_info_name | text | yes | — | Authorized pickup person's name. |
| will_call_info_email | text | yes | — | Contact email for pickup notification. |
| will_call_info_phone | text | yes | — | Contact phone for pickup notification. |
| sales_order_id | uuid | yes | — | **Conversion Link**: The resulting SO once project is `SOLD`. |
| creator_id | uuid | yes | — | The user who registered the quote. |
| credit_terms_id | uuid | yes | — | Link to `credit_terms.id` (Net 30, etc.). |
| expedite_fee | numeric(12,2) | no | — | Surcharge for priority lead times. |
| expedite | bool | no | — | Flag for priority processing. |
| commission_base_amount_manual_adjustment | numeric(12,2) | no | — | Manual override of the amount used for commission math. |
| regular_commission_percentage | numeric(12,2) | no | — | Standard commission rate for this deal. |
| overage_commission_percentage | numeric(12,2) | no | — | Surcharge/High-margin commission rate. |
| commission_base_amount | numeric(12,2) | no | — | The total order value subject to commission. |
| regular_commission | numeric(12,2) | no | — | Calculated dollar value for regular commission. |
| discount_amount | numeric(12,2) | no | — | Total dollar discount applied to the proposal. |
| overage_commission | numeric(12,2) | no | — | Calculated dollar value for overage commission. |
| tariff_amount | numeric(12,2) | no | — | Total import/regulatory duties. |
| tax_amount | numeric(12,2) | no | — | Total estimated sales tax. |
| taxable_subtotal | numeric(12,2) | no | — | Value of all itemized taxable components. |
| non_taxable_subtotal | numeric(12,2) | no | — | Value of all service/non-taxable components. |
| freight_cost | numeric(12,2) | no | — | Estimated shipping and handling fees. |
| total_overage | numeric(12,2) | no | — | Overage amount from specific line pricing. |
| total_commission | numeric(12,2) | no | — | **Total Payout**: Rollup of all commissions. |
| order_total | numeric(12,2) | no | — | **Grand Total**: The final amount presented to customer. |
| customer_po_number | text | yes | — | The ID the customer assigns to their purchase order. |
| customer_po_amount | numeric(12,2) | yes | — | The amount the customer authorized in their PO. |
| customer_po_received_by_id | uuid | yes | — | User who verified the customer's PO document. |
| customer_po_received_date | int8 | yes | — | Date the customer's PO was received. |
| in_relation_to_field_service_ticket_id | uuid | yes | — | Link to a Field Service Ticket if the quote is for repair parts. |
| in_relation_to_sales_order_id | uuid | yes | — | Link to a larger SO if this is a sub-quote or revision. |
| in_relation_to_unit_id | uuid | yes | — | Link to a physical asset/unit being quoted for repair. |
| tax_rate | numeric(12,2) | no | — | The tax percentage applied. |
| tariff_rate | numeric(12,2) | no | — | The tariff percentage applied. |
| discount_rate | numeric(12,2) | no | — | The overall discount percentage for the project. |
| on_hold_for_release | bool | no | — | If `true`, the quote is waiting for engineering or client release. |
| project_name | text | yes | — | Short name for the project (e.g., "Airport HVAC Tower A"). |
| description | text | yes | — | General scope of work. |
| confirm_info_is_total_order_confirmed | bool | no | — | Client confirmed the final price. |
| special_instruction | text | no | — | Delivery or technical notes for the project. |
| check_status | enum | no | — | Indicator for physical deposit checks. |
| project_location | text | yes | — | Physical destination or job site location. |
| confirm_info_is_billing_address_confirmed | bool | no | — | Client confirmed the billing address. |
| confirm_info_is_shipping_address_confirmed | bool | no | — | Client confirmed the shipping address. |
| confirm_info_is_client_confirmed | bool | no | — | Client confirmed their account settings. |
| confirm_info_confirm_date | int8 | yes | — | Date the formal confirmation was received. |
| confirm_info_confirmed_by_id | uuid | yes | — | The internal user who authenticated the confirmation. |
| confirm_info_confirmed_by_name | text | yes | — | Name of the specific customer contact who approved. |
| billing_address_state | text | no | — | State for customer invoicing. |
| shipping_address_state | text | no | — | Destination state for the products. |
| freight_terms | text | no | — | Terms of transport (e.g., "Prepaid", "Collect"). |
| project_id | uuid | yes | — | Link to the parent project, if the quote belongs to one. |
| transfered | bool | no | — | If `true`, the quote data has been synchronized with an external system. |
| made_by_another_store | bool | no | — | If `true`, the quote was created by another store (inter-store purchase quote). |
| type | enum | no | — | **Quote class** (`quote_type_enum`): `SALES` or `FIELD_SERVICE`. |
| lead_time_name | text | yes | — | Human-readable lead time (e.g., "7-10 Days"). |
| lead_time_id | uuid | yes | — | Link to `leadtimes.id`. |
| made_via_client_panel | bool | no | — | If `true`, the quote originated from the client-facing panel rather than staff entry. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |
| is_active | bool | no | — | Global visibility flag. If `false`, the quote is soft-deleted/hidden. |
| is_fully_confirmed | bool | no | — | If `true`, every `confirm_info_...` verification step has been completed. |
| made_by_client | bool | no | — | If `true`, the quote was submitted by the client themselves. |

## Enums Used

### `quote_check_enum`
(Live DB values): `NEWLY_CREATED`, `NOT_CHEKCED`, `MATCH`, `MISMATCH`.

### `quote_status_enum`
(Live DB values): `REQUESTED`, `NEW`, `PENDING`, `SOLD`, `CANCELLED`, `EXPIRED`, `REVISED`.

### `quote_type_enum`
(Live DB values): `SALES`, `FIELD_SERVICE`.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| client_id | clients | id | cascade |
| creator_id | users | id | cascade |
| sales_order_id | sales_orders | id | set null |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| quote_line_items | quote_id | The specific SKU itemization of the proposal. |
| sales_orders | quote_id | The parent source that was converted into this order. |

## Common Query Patterns
```sql
-- Find all outstanding project quotes exceeding $50,000 for a revenue forecast
SELECT project_name, order_total, expire_date 
FROM quotes 
WHERE status = 'PENDING' AND order_total > 50000;

-- List quotes converted to Sales Orders this month
SELECT number, sales_order_id, confirm_info_confirm_date 
FROM quotes 
WHERE status = 'SOLD' AND confirm_info_confirm_date > EXTRACT(EPOCH FROM (NOW() - INTERVAL '30 days'));
```

## Indexes
- *Uses a btree index on `number` for high-performance CRM searching.*
