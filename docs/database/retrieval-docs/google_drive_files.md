# google_drive_files

## Purpose
The external cloud sync registry. It manages technical references to documents hosted on Google Drive, allowing the ERP to integrate with live Google Sheets used by customers or engineers for project data, surveys, or mass updates.

---

## Retrieve This Table When The User Asks About

**Cloud documents and drive links**
External attachments or shared docs hosted exclusively on Google Drive. Listing all live Google Sheets linked to a specific branch or project. (Note: For general cloud storage or S3 file attachments, use `files` instead).

**Remote file integration**
Retrieving Google-native file IDs used for "pulling" live data into ERP internal tables (e.g., during import reports). Verifying technical file formats (mime_type) for cloud assets.

**Audit of cloud links**
Identifying recently updated external file references. Auditing which branch owns a specific Google Sheet link.

---

## Co-Retrieved Sibling Tables
- `stores` — the branch that owns the external file link.
- `import_reports` — processes that consume data from these cloud links.
