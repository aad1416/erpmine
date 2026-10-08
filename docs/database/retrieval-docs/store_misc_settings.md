# store_misc_settings

## Purpose
The digital storefront curation engine. It acts as a mini-CMS for each branch, defining the frontend presentation, marketing highlights, and curated product categories displayed on the store's web layout.

---

## Retrieve This Table When The User Asks About

**Storefront personalization and CMS data**
Local overrides or miscellaneous storefront settings. Identifying which categories (e.g., "Popular Categories") or items are featured on the homepage.

**Marketing curation and promotional items**
Retrieving curated lists of "Special Offer" items or "Latest Categories" for promotional display. Identifying the design/UI template used by a specific branch.

**Frontend navigation and UI layout**
Finding the user-selected categories for website navigation. Auditing the technical profile of curated storefront rows.

---

## Co-Retrieved Sibling Tables
- `stores` — the branch owning the digital storefront.
- `ds_templates` — the digital UI template being used.
- `categories` — the taxonomies featured in the curation lists.
- `item_stores` — the specific items on special offer or highlighted.
