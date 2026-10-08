# import_report_full_report_row

## Purpose
The forensic error ledger. It stores granular, row-by-row failures that occur during bulk data imports, allowing administrators to identify and correct specific lines in their source documents (Excel/CSV) without crashing the entire job.

---

## Retrieve This Table When The User Asks About

**Data import details and entry verification**
Migration logs or spreadsheet row failures. Listing the specific error messages (e.g., "Invalid SKU") and physical row numbers for a failed job.

**Data recovery and offending values**
Retrieving the raw problematic string (value) exactly as found in the source file to facilitate correction.

**Error trend analysis**
Identifying the most common data entry errors (e.g., "Missing Mandatory Field") across all historical imports.

---

## Co-Retrieved Sibling Tables
- `import_reports` — the parent ingestion job header.
