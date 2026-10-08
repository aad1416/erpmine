# units

## Purpose
The "As-Built" physical asset registry. It defines every unique, serialized machine in the system, tracking its entire lifecycle from initial order and production to delivery and long-term field service history.

---

## Retrieve This Table When The User Asks About

**Physical assets and serial numbers**
Individual machines, serialized products, or unique equipment instances. Searching for a specific machine using its serial number or model number combination.

**Production status and manufacturing lifecycle**
Tracking the current state of a machine (Ordered, In Progress, Ready to Ship, Shipped, Delivered). Monitoring which units are currently on the production floor (Issued) vs those awaiting quality inspection.

**Financial accumulation and profitability**
Calculating the exact profitability of a specific serial number. Finding accumulated labor costs, material (part) costs, and overhead tariffs for a unique build. Identifying variances between estimated and actual manufacturing costs.

**Logistics and field readiness**
Checking if a unit is "Ready to Ship" (QC passed). Finding the actual ship date or estimated delivery window for a specific machine.

**Fleet and service history**
Identifying all machines delivered to a specific customer (Sales Order link). Using a unit record as the anchor for service tickets, maintenance, and warranty claims.

---

## Co-Retrieved Sibling Tables
- `sales_orders` — the commercial contract for the machine.
- `unit_bom_records` — the "As-Built" internal DNA of the unit.
- `production_tasks` — the active work orders on the shop floor.
- `timelogs` — the recorded human effort for the build.
- `field_service_tickets` — the technical history of the asset.
