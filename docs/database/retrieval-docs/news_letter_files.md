# news_letter_files

## Purpose
The attachment junction for mass-communication. It links newsletter campaigns to the global files repository, allowing marketing teams to efficiently reuse technical documents or flyers without duplicating physical data.

---

## Retrieve This Table When The User Asks About

**Campaign attachments and newsletter media**
Marketing files or supplemental documents. Listing all PDF attachments physically included in a specific email blast.

**Delivery toggles**
Identifying which files are linked but physically excluded from delivery (is_attached flag). Auditing which store branches are attaching a specific global document.

---

## Co-Retrieved Sibling Tables
- `news_letters` — the parent marketing campaign.
- `files` — the actual physical document or image payload.
