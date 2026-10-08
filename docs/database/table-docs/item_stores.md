# `item_stores`

## Searchable Aliases
branch catalog, local products, store items, branch inventory, stocking units

## Description
The `item_stores` table is the **SKU-level (Branch Specific)** registry for the **Lyndom** (the current PostgreSQL ERP) system. While the `items` table represents a global blueprint, `item_stores` acts as the operational master for a product at a specific physical store or warehouse, acting as the primary source for the **e-commerce catalog** and **website listed items**. It contains **83 columns** that govern the core "Business Logic" of the ERP, including tiered pricing, inventory valuation (FIFO), replenishment automation, and multi-pillar manufacturing costs.

## ⚠️ SQL-Critical Behaviors
- **Tenant Partitioning**: Global product data (`items`) is useless for inventory without joining to `item_stores` via `item_id` and filtering by `store_id`.
- **The "Cost-Margin" Bridge**: The `total_cost` is a calculated aggregate of `part_cost`, `labor_cost`, and `overhead`. This value is the baseline for all gross margin reports.
- **Stock Availability Logic**: Available Stock = `on_hand_quantity` - `allocated_quantity`. You cannot reliably fulfill an order based on "On Hand" alone.
- **Workflow Approvals**: Specialized boolean gates (`sales_approval`, `shipping_approval`) allow management to block the sale or dispatch of items that are incomplete or under technical review.

## Columns (87 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of registration. |
| updated_at | timestamptz | no | — | Timestamp of last modification. |
| store_id | uuid | no | — | The branch ownership. Enforces tenant isolation. |
| no | text | no | — | **Branch SKU Number**. The local part number physically used in the warehouse. |
| name | text | no | — | The display name for this location. Often localized or branch-specific. |
| description | text | no | — | Detailed product description for quotes and sales orders. |
| category_id | uuid | yes | — | The taxonomy node (`categories.id`) that governs this item's technical rules. |
| barcode | text | no | — | The Scannable code used for warehouse receiving and pick-and-pack. |
| length | numeric(12,2) | yes | — | Physical length used for freight volume calculations. |
| width | numeric(12,2) | yes | — | Physical width used for freight volume calculations. |
| height | numeric(12,2) | yes | — | Physical height used for freight volume calculations. |
| length_unit | text | yes | — | Unit of measure for dimensions (e.g., "inches"). |
| weight | numeric(12,2) | yes | — | Physical weight used for shipping weight and freight cost estimates. |
| weight_unit | text | yes | — | Unit of measure for weight (e.g., "lbs"). |
| item_id | uuid | no | — | Link to the global product blueprint (`items.id`). |
| count_by | enum | no | — | **Inventory Mode**: `SERIAL` (individual units) vs. `QUANTITY` (bulk tracking). |
| recent_purchase_price_by | numeric(12,2) | no | — | The price paid on the most recent Purchase Order for this item. |
| price_multiplier | numeric(12,2) | no | — | A coefficient applied to the base price for flexible markup/markdown logic. |
| price | numeric(12,2) | no | — | **List Price**: The primary selling price offered to customers. |
| allocated_quantity | numeric(12,2) | no | — | **Reserved Stock**: Items physically in the warehouse but sold to a customer. |
| allocated_quantity_uom | numeric(12,2) | no | — | The allocated total expressed in its specific primary UOM. |
| archived | bool | no | — | If `true`, the SKU is soft-deleted and hidden from active Sales/Inventory lists. |
| archived_date | int8 | yes | — | Epoch timestamp of archival. |
| on_hand_quantity | numeric(12,2) | no | — | **Physical Stock**: Total units currently sitting on warehouse shelves. |
| on_hand_quantity_uom | numeric(12,2) | no | — | The total physical count expressed in its specific primary UOM. |
| on_order_quantity | numeric(12,2) | no | — | **Incoming Stock**: Units currently on open Purchase Orders from vendors. |
| on_order_quantity_uom | numeric(12,2) | no | — | The expected total expressed in its specific primary UOM. |
| fifo_value | numeric(12,2) | no | — | **Inventory Asset Value**: Calculated using First-In-First-Out logic. |
| on_hand_total_value | numeric(12,2) | no | — | Total dollar value of currently stored physical inventory. |
| do_not_track_quantity | bool | no | — | If `true`, the system ignores stock level checks (used for generic/expensed items). |
| sales_approval | bool | no | — | Commercial gate: if `false`, the item cannot be quoted/sold without administrative override. |
| shipping_approval | bool | no | — | Logistics gate: if `false`, the item cannot be shipped or picked. |
| note | text | yes | — | Internal operational or technical notes for warehouse/sales staff. |
| lead_time | numeric(12,2) | no | — | Estimated days required for replenishment from a vendor or production. |
| reorder_quantity | numeric(12,2) | no | — | **Standard Lot Size**: The amount typically bought/built when stock is low. |
| trigger_quantity | numeric(12,2) | no | — | **The Order Point**: If `available` hits this level, a reorder alert is generated. |
| online_sale_quantity | numeric(12,2) | no | — | Stock reserved specifically for dedicated online/eCommerce channels or website listed items. |
| use_tariff_for_purchasing | bool | no | — | If `true`, the system automatically applies `tariff_amount` logic to new POs. |
| main_uom_id | uuid | yes | — | Link to `uoms.id` defining the primary unit of measure (e.g., "Each"). |
| taxable | bool | no | — | Determines if Sales Tax should be applied to this item during checkout. |
| dont_order_on_purchase_orders | bool | no | — | Procurement block: ensures this item is never added to external purchase orders. |
| rnd_only | bool | no | — | Restriction flag for Research & Development items (not for general sale). |
| obsolete | bool | no | — | Discontinuance flag: SKU is no longer supported or saleable. |
| field_service_item | bool | no | — | If `true`, available for dispatchers to add to Field Service Tickets. |
| non_inventory_item | bool | no | — | Expensed items (consumables) that have no physical value logic. |
| is_active | bool | no | — | Main status flag for software visibility. |
| has_bom | bool | no | — | If `true`, this SKU is a finished assembly with a Bill of Materials in `boms`. |
| override | numeric(12,2) | no | — | Manual cost override value provided by management. |
| override_use | bool | no | — | If `true`, the system uses the `override` field instead of standard cost for margins. |
| part_cost | numeric(12,2) | no | — | **Material Basis**: The unit cost of the physical raw components. |
| labor_cost | numeric(12,2) | no | — | **Transformation Basis**: The cost of man-hours to build this assembly. |
| total_cost | numeric(12,2) | no | — | **The Final Cost**: Sum of Part + Labor + Overhead + Override logic. |
| preferred_vendor_id | uuid | yes | — | The default supplier (`vendors.id`) used for automated replenishment. |
| pricing | jsonb | no | — | Extensible array for advanced branch-level pricing rules and tiers. |
| creator_id | uuid | no | — | The user identity responsible for registering this SKU listing. |
| is_manufactured | bool | no | — | If `true`, the SKU is built in-house from components rather than purchased. |
| item_type_id | uuid | yes | — | Foreign key to `item_types.id` for high-level ERP classification. |
| labor_time | numeric(12,2) | yes | — | The man-hour estimate used to calculate `labor_cost`. |
| is_on_sale | bool | no | — | Toggle to activate the `on_sale_price` for promotional periods. |
| on_sale_price | numeric(12,2) | no | — | Promotional price used if `is_on_sale` is active. |
| gl_code | text | yes | — | **Accounting Key**: General Ledger code for financial integration. |
| gl_description | text | yes | — | **Accounting Key**: Text description of the General Ledger account. |
| default_location_id | uuid | yes | — | Primary warehouse bin/zone (`locations.id`) where this item is stored. |
| preferred_vendor_sku | text | yes | — | The vendor's own catalog number (used for printing clear POs). |
| spec_rule_flag | bool | no | — | Logic trigger: if `true`, it follows item selection rules in `spec_rules`. |
| spec_rule_id | uuid | yes | — | Link to the automation logic that governs this item's configuration. |
| item_config_is_option | bool | no | — | Component Type: Physical configurable upgrade/option. |
| overhead | numeric(12,2) | no | — | **Fixed Cost Basis**: Operational drag (utilities, rent) applied to this CPU. |
| tariff_amount | numeric(12,2) | no | — | The custom duty or import tariff value applied during procurement. |
| item_config_is_service | bool | no | — | Component Type: Non-physical service/labor. |
| item_config_is_warranty | bool | no | — | Component Type: Time-based service guarantee. |
| item_config_is_assembly | bool | no | — | Component Type: Manufactured product with a BOM. |
| item_config_is_spare_parts | bool | no | — | Component Type: Repair and maintenance component. |
| used_in_last90_days | int4 | no | — | **Velocity Metric**: Number of transactions in the last 90 days. |
| used_in_last365_days | int4 | no | — | **Velocity Metric**: Number of transactions in the last 365 days. |
| used_in_last180_days | int4 | no | — | **Velocity Metric**: Number of transactions in the last 180 days. |
| last_count | int8 | yes | — | Epoch timestamp of the last physical inventory audit/cycle count. |
| last_used_in_a_job | int8 | yes | — | Epoch timestamp of the last time this SKU was issued to a Manufacturing Job. |
| not_shippable | bool | no | — | If `true`, identifies Labor or Service items that do not require physical logistics. |
| shipping_checklist_not_required | bool | no | — | Bypasses the warehouse quality control / item-check step for this SKU. |
| is_public | bool | no | — | If `true`, the item is visible in the client-facing panel/catalogue. |
| labor_cost_per_hour | numeric(12,2) | no | — | Hourly labor rate used when costing manufactured items. |
| lead_time_history | jsonb | no | — | jsonb array of `{mode, value, receiveId}` lead-time samples (days) observed at receiving. **Sparse**: non-empty on ~7 of ~540k rows — not usable as a lead-time source; use `vending.lead_time`. |
| is_created_by_matrix | bool | yes | — | If `true`, the SKU was generated by the product-matrix (variant) tool. |
| engineering_approval | bool | no | — | If `true`, engineering has signed off the item for production/sale. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Enums Used

### `count_by_enum`
(Live DB values): `SERIAL`, `QUANTITY`.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| item_id | items | id | cascade |
| category_id | categories | id | set null |
| main_uom_id | uoms | id | set null |
| preferred_vendor_id | vendors | id | set null |
| spec_rule_id | spec_rules | id | set null |
| default_location_id | locations | id | set null |

## Common Query Patterns
```sql
-- Inventory Asset Report
SELECT name, on_hand_quantity, fifo_value, on_hand_total_value 
FROM item_stores 
WHERE store_id = '<uuid>';

-- Gross Margin Basis calculation
SELECT name, price, total_cost, (price - total_cost) as gross_margin 
FROM item_stores 
WHERE price > 0;
```

## Indexes
- *Includes 10 btree indexes optimized for high-velocity lookups on `no`, `store_id`, `name`, and `archived` status.*
