# `purchase_orders`

## Searchable Aliases
buy orders, procurement contracts, vendor orders, inbound shipments, po header

## Description
The `purchase_orders` (PO) table is the authoritative header for the procurement of goods and services within the **Lyndom** (the current PostgreSQL ERP) system. It acts as a formal contract between the business and a **Vendor**, defining the financial totals, shipping destinations, and the current state of fulfillment.

A Purchase Order serves as the root record for tracking vendor lead times, accounts payable liabilities, and incoming stock arrivals.

## ⚙️ The Procurement Workflow
1.  **Preparation**: A Buyer creates a PO in `PENDING` status, defining the items, quantities, and a `required_by` date.
2.  **Approval**: The PO is submitted for internal review (`is_approved`). Once authorized by a manager (`approved_by_id`), it is sent to the vendor.
3.  **Acknowledgment**: The vendor confirms the order and providing an estimated delivery date (`acknowledge_date`). status moves to `ACKNOWLEDGED`.
4.  **Transit**: The vendor ships the goods and providing a `tracking_number`. The system monitors the `estimated_delivery_date`.
5.  **Fulfillment**: As goods arrive at the loading dock, the status moves to `PARTIALLY_RECEIVED` or `RECEIVED`, triggering the creation of a `receives` record.

## ⚠️ SQL-Critical Behaviors
- **Total Math**: The `order_total` is a rollup of all line items plus `freight_cost`, `expedite_fee`, and `tax_amount`, minus any `discount_amount`.
- **Status Enum**: Management of the order depends on the value in `status`. (Actual values include: `PENDING`, `ACKNOWLEDGED`, `STAGED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CANCELLED`, `HOLD`).
- **Payment Linkage**: The `payment_completion_status` and `paid_amount` track the financial settlement of the PO, bridging the gap between the Warehouse and the Accounting department.
- **Payment completion enum** (`payment_completion_status`): use only **`FULLY_PAID`**, **`PARTIALLY_PAID`**, **`UNPAID`** — there is no `PAID` value. Filter unpaid orders with `= 'UNPAID'` or not fully settled with `!= 'FULLY_PAID'` (includes partial).
- **Legacy Fingerprint**: If `is_imported = true`, the order was migrated from the legacy **Phocuss** (legacy MongoDB ERP) system.

## Columns (65 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch issuing the purchase order. |
| purchase_date | int8 | no | — | The date the order was officially placed (Epoch). |
| number | text | no | — | **Human-Readable ID**: The serial number of the PO (e.g., PO-1023). |
| vendor_id | uuid | no | — | Link to `vendors.id` for the supplier. |
| acknowledge_date | int8 | yes | — | Date the vendor confirmed the order. |
| status | enum | no | — | **Lifecycle State**: (e.g., `PENDING`, `PARTIALLY_RECEIVED`, `RECEIVED`). |
| received_date | int8 | yes | — | The date the last item was successfully received. Epoch ms. Sparsely populated — for actual delivery dates use MAX(receives.received_at) per purchase order instead. |
| order_total | numeric(12,2) | no | — | **Grand Total**: The final dollar amount owed to the vendor (rollup of line items plus `freight_cost`, `expedite_fee`, `tax_amount`, minus `discount_amount`). **Use this alone for PO value**: populated on ~92% of rows, whereas the subtotal split is not. |
| actual_delivery_date | int8 | yes | — | The date the shipping carrier delivered the goods. Epoch ms. Sparsely populated — do not use for lead-time or delivery analysis; use MAX(receives.received_at) per purchase order instead. |
| description | text | yes | — | High-level summary of the purchase intent. |
| note | text | yes | — | Internal-only instructions or audit comments. |
| is_active | bool | no | — | Global visibility flag. |
| billing_address_city | text | no | — | Billing city for the vendor invoice. |
| billing_address_address | text | no | — | Full street address for billing. |
| billing_address_latitude | numeric(12,2) | yes | — | Geographical coordinates for billing. |
| billing_address_longitude | numeric(12,2) | yes | — | Geographical coordinates for billing. |
| billing_address_postal_code | text | yes | — | Billing ZIP/Postal code. |
| billing_address_building_number | text | yes | — | Billing building ID. |
| billing_address_unit | text | yes | — | Billing suite/unit. |
| shipping_address_city | text | no | — | Warehouse city where goods will arrive. |
| shipping_address_address | text | no | — | Full street address for delivery. |
| shipping_address_latitude | numeric(12,2) | yes | — | Geographical coordinates for shipping. |
| shipping_address_longitude | numeric(12,2) | yes | — | Geographical coordinates for shipping. |
| shipping_address_postal_code | text | yes | — | Shipping ZIP/Postal code. |
| shipping_address_building_number | text | yes | — | Shipping building/gate ID. |
| shipping_address_unit | text | yes | — | Shipping warehouse unit. |
| estimated_delivery_date | int8 | yes | — | The ETA provided by the vendor. |
| payment_completion_status | enum | no | — | AP payment state: `UNPAID`, `PARTIALLY_PAID`, or `FULLY_PAID` only. |
| paid_amount | numeric(12,2) | no | — | Total dollar amount settled with the vendor to date. |
| required_by | int8 | yes | — | The deadline for the goods to be in the warehouse. |
| creator_id | uuid | no | — | The Buyer who registered the order. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |
| is_sent_to_vendor_store | bool | no | — | If `true`, indicates EDI or B2B transmission to the supplier. |
| discount_amount | numeric(12,2) | no | — | Flat dollar amount deducted from the total. |
| tax_amount | numeric(12,2) | no | — | Calculated dollar amount of tax. |
| tariff_amount | numeric(12,2) | no | — | Import or specialized tariff fees added to the cost. |
| total_overage | numeric(12,2) | no | — | Buffer amount allowed for slight shipping quantity variations. |
| expedite | bool | no | — | If `true`, the order is marked for priority shipping. |
| expedite_fee | numeric(12,2) | no | — | The surcharge paid for expedited processing. |
| freight_cost | numeric(12,2) | no | — | The shipping/transportation fee charged by the vendor. |
| tracking_number | text | yes | — | The carrier's tracking ID (FedEx, UPS, etc.). |
| purchase_order_type_id | uuid | yes | — | Category of PO (e.g., `CAPITAL_EQUIPMENT`, `STOCKED_PART`). |
| is_estimated | bool | no | — | If `true`, costs are placeholders until actual invoice arrival. |
| discount_rate | numeric(12,2) | no | — | Percentage discount applied to the total order. |
| tax_rate | numeric(12,2) | no | — | Sales tax percentage. |
| check_status | enum | no | — | Tracking indicator for physical check payments. |
| former_status | enum | yes | — | The previous state of the PO before the last update. |
| overhead | numeric(12,2) | no | — | General handling or administrative fees. |
| in_relation_to_field_service_ticket_id | uuid | yes | — | Link to a specific Field Service Ticket that required these parts. |
| is_approved | bool | yes | — | Managerial authorization flag. |
| approved_by_id | uuid | yes | — | The manager identity who authorized the purchase. |
| billing_address_state | text | no | — | Billing state for the vendor invoice. |
| shipping_address_state | text | no | — | Warehouse state where goods will arrive. |
| external_sales_order_id | uuid | yes | — | Link to the counterpart `sales_orders.id` in the *selling* store for inter-store purchases. |
| dropship | bool | no | — | If `true`, the vendor ships directly to the end customer; goods never enter this store's warehouse. |
| vendor_so_number | text | yes | — | The vendor's own sales-order number for this PO (vendor-side mirror of `customer_po_number`). |
| vendor_so_amount | numeric(12,2) | yes | — | The amount on the vendor's sales-order confirmation. |
| vendor_so_received_by_id | uuid | yes | — | User who recorded the vendor's SO confirmation. |
| vendor_so_received_date | int8 | yes | — | Epoch timestamp when the vendor's SO confirmation was received. |
| tariff_rate | numeric(12,2) | no | — | Import tariff percentage applied to tariffable line items on this PO. |
| taxable_subtotal | numeric(12,2) | no | — | Sum of taxable line items. **Effectively unpopulated** (<1% of rows non-zero) and does not reconcile with `order_total` — do not use for reporting. |
| non_taxable_subtotal | numeric(12,2) | no | — | Sum of non-taxable line items/services. **Effectively unpopulated** (<1% of rows non-zero) — do not use for reporting. |

## Enums Used

### `purchase_order_check_enum`
(Live DB values): `NEWLY_CREATED`, `NOT_CHEKCED`, `MATCH`, `MISMATCH`.

### `purchase_order_entity_former_status_enum`
(Live DB values): `PENDING`, `ACKNOWLEDGED`, `STAGED`, `PARTIALLY_STAGED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CANCELLED`, `HOLD`, `DROPSHIP`.

### `purchase_order_entity_status_enum`
(Live DB values): `PENDING`, `ACKNOWLEDGED`, `STAGED`, `PARTIALLY_STAGED`, `PARTIALLY_RECEIVED`, `RECEIVED`, `CANCELLED`, `HOLD`, `DROPSHIP`.

### `purchase_order_payment_completion_status_enum`
(Live DB values): `FULLY_PAID`, `PARTIALLY_PAID`, `UNPAID`.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| vendor_id | vendors | id | cascade |
| creator_id | users | id | cascade |
| approved_by_id | users | id | set null |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| purchase_order_line_items | purchase_order_id | The specific items ordered on this PO. |
| receives | purchase_order_id | Receiving vouchers linked to this contract. |

## Common Query Patterns
```sql
-- Find all Open/Pending orders that are past their Required Date
SELECT number, vendor_id, required_by 
FROM purchase_orders 
WHERE status NOT IN ('RECEIVED', 'CANCELLED') 
  AND required_by < EXTRACT(EPOCH FROM NOW());

-- Calculate the total outstanding AP (not fully paid) across all orders
SELECT SUM(order_total - paid_amount) 
FROM purchase_orders 
WHERE payment_completion_status IN ('UNPAID', 'PARTIALLY_PAID');
```

## Indexes
- *Uses 5 btree indexes on `number`, `status`, `vendor_id`, `store_id`, and `purchase_date` for rapid procurement reporting.*
