# `option_selectors`

## Searchable Aliases
configuration rules, automated add-ons, item mapping, product logic engine

## Description
The `option_selectors` table manages the automation rules for appending optional upgrades and modular components to a product configuration. While `service_selectors` handle non-physical labor/fees, `option_selectors` focus on physical parts or system upgrades (e.g., "Add Premium Enclosure if Outdoor is selected"). It serves as the "Header" for the option-matching engine, allowing branches to define complex upgrade logic based on the technical specifications of a base product.

## ⚠️ SQL-Critical Behaviors
- **Upgrade Logic Header**: Stores metadata for the option selection process. The technical matching is handled via `option_selector_sources` and `option_selector_destinations`.
- **Branch Customization**: Scoped to `store_id`, allowing different locations to offer different automated upgrades.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| label | text | no | — | Human-readable rule name (e.g., "Standard Enclosure Matcher"). |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| description | text | yes | — | Context for the option selection logic. |
| creator_id | uuid | no | — | The user who registered this selector. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| option_selector_sources | option_selector_id | Defines the "If" conditions (Source Specs). |
| option_selector_destinations | option_selector_id | Defines the "Then" result (Destination Specs for an Option Item). |

## Common Query Patterns
```sql
-- List all active upgrade selectors for a store
SELECT label FROM option_selectors WHERE store_id = '<uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*
