# specifications

## Purpose
The engineering attribute registry. It defines the technical "Question" (e.g., Voltage, Power Rating) for items within specific categories, serving as the technical schema for product datasheets.

---

## Retrieve This Table When The User Asks About

**Technical fields and engineering parameters**
Attribute registry, technical datasheet keys, or product attribute definitions. Identifying which technical fields (e.g., "Frequency", "Secondary Voltage") are valid for a particular product category.

**Data types and valid units**
Identifying the technical data types (String, Number, Boolean) and valid unit picklists (e.g., VAC, Hz) allowed for an attribute. 

**High-level search and filtering attributes**
Identifying primary attributes used for searching or filtering products in the catalog (is_primary flag).

---

## Co-Retrieved Sibling Tables
- `categories` — the product taxonomy these attributes belong to.
- `item_specifications` — the actual technical values assigned to items.
- `item_store_specifications` — branch-specific technical values.
