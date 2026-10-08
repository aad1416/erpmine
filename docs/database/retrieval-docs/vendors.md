# vendors

## Purpose
The master repository for all supply-side entities, including manufacturers, wholesalers, and technical subcontractors. It manages the procurement lifecycle and tracks technical service partners across the ERP.

---

## Retrieve This Table When The User Asks About

**Suppliers and procurement partners**
Master registry of vendors, wholesalers, or accounts payable entities. Legal company names used on purchase orders and financial checks. Tracking active vs blocked (frozen) suppliers.

**Technical service providers and contractors**
Specialist engineers or technical subcontractors (is_tech flag) used for maintenance and field service. Finding vendors who provide labor or services instead of physical goods.

**Contact and sourcing location information**
Primary sales reps or account managers at a supplier. Vendor corporate websites and email addresses for sending POs. Supplier headquarters or warehouse addresses for freight and lead-time calculations.

**Internal branch relationships**
Identifying vendors that are related business entities or other internal branches. Tracking who registered the supplier relationship.

---

## Co-Retrieved Sibling Tables
- `purchase_orders` — orders issued to this supplier.
- `vending` — the specific items and costs sourced from this vendor.
- `contacts` — individual reps or technicians linked to the vendor organization.
- `stores` — the branch managing the supplier relationship.
