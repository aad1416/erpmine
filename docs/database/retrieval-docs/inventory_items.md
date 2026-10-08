# inventory_items

## Purpose
The atomic registry for physical stock. It tracks the physical reality of inventory on the shelf, including individual serialized units and bulk quantities stored in specific warehouse bins.

---

## Retrieve This Table When The User Asks About

**Stock levels and physical inventory**
Current quantity on hand, net stock, or physical availability of a product. Finding exactly how many units of a specific SKU are currently in the building. Tracking total count (available + issued) vs net shelf availability.

**Bin locations and storage**
Warehouse items, bin locations, or shelf positions for specific parts. Finding which warehouse zone, shelf, or bin contains a particular item or serial number.

**Serialized unit tracking**
Manufacturer serial numbers, internal serial numbers, or unique physical machines in stock. Finding the exact warehouse slot for a piece of equipment by scanning its OEM tag or serial number.

**Stock sourcing and audit trails**
Identifying the procurement source (purchase order) or receiving event that brought a specific item into the building. Finding which receiving voucher or line item created a particular stock record.

**Commitments and issued stock**
Units physically removed from a bin for a manufacturing job or shipment (issued quantity). Tracking stock that is committed but not yet officially removed from the inventory ledger.

**Condition and metadata**
Hardware revisions, condition notes, or extensible metadata for physical units. Identifying when a unit was last updated or moved.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch-specific SKU definition.
- `locations` — the specific bin or warehouse zone.
- `receives` — the arrival event that created the stock.
- `purchase_orders` — the buy order that sourced the stock.
- `cycle_counts` — the most recent verification of this stock record.
