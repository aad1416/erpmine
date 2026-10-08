# cross_checks

## Purpose
The technical validation hub. It manages the rules for comparing external engineering data—such as CAD exports or site surveys—against internal technical standards to identify incompatibilities or design violations before production.

---

## Retrieve This Table When The User Asks About

**Engineering validation and error checking**
Consistency rules, audit flags, or system alerts for design files. Initiating a "Project Compatibility Check" against an uploaded document.

**Transactional data auditing**
Identifying discrepancies, missing specs, or design-rule violations in external vendor catalogs or site-survey spreadsheets. Using standardized audit libraries (e.g., "UL Safety Standard Audit").

**File-based technical audits**
Linking a specific technical audit (label) to an uploaded design file. Segregating engineering standards by branch (e.g., USA vs. EU standards).

---

## Co-Retrieved Sibling Tables
- `cross_check_applies_to` — the individual technical criteria used for filtering.
- `files` — the uploaded design or engineering document being audited.
- `users` — the engineer or manager conducting the audit.
