# files

## Purpose
The central media repository and attachment engine. It acts as the universal hub for every binary asset in the application—from product photos and technical drawings to PDFs and customer signatures—using polymorphic links to anchor documents to domain records.

---

## Retrieve This Table When The User Asks About

**Documents and attachments**
Uploads, images, digital assets, cloud storage, AWS S3, or cloud files. Retrieving all files (PDFs/images/cloud documents) attached to a specific Sales Order, Item, or Vendor record.

**Polymorphic file links**
Identifying attachments by their target record ID (owner_id) and type (owner_type). Finding technical manuals, site survey results, or product labels.

**Asset ownership and authoring**
Identifying the user (creator) who uploaded a specific document. Filtering for branch-specific sensitive files or global product images.

**MIME types and classification**
Finding files of a specific format (e.g., application/pdf vs image/jpeg). Auditing file uploads by a specific user across different ERP modules.

---

## Co-Retrieved Sibling Tables
- `stores` — the branch that owns or uploaded the asset.
- `users` — the author who uploaded the file.
- `items` / `sales_orders` / `vendors` — the records being annotated with attachments (polymorphic).
