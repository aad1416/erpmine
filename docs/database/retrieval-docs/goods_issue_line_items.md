# goods_issue_line_items

## Purpose
The atomic record of warehouse consumption. It identifies the specific physical items—including batch, serial number, and source bin—that were removed from inventory during an issuance event.

---

## Retrieve This Table When The User Asks About

**Issued items and parts withdrawal**
Component allocation details, material withdrawal lists, or stock consumption specifics. Identifying exactly what was removed from stock in a particular goods issue.

**Specific inventory depletion**
Tracking which physical inventory record (bin and instance) was subtracted from. Capturing the exact batch or serial number removed for a job.

**Traceability for builds and repairs**
The point of origin for material cost rollups to a unit build or field service repair. Linking specific physical parts to their final consumption destination.

---

## Co-Retrieved Sibling Tables
- `goods_issues` — the parent issuance header.
- `inventory_items` — the physical stock record that was decremented.
- `job_records_issue_line_items` — the link to an engineering BOM record.
- `users` — the staff member who performed the digital out-scan.
