# `guilds`

## Searchable Aliases
communities, groups, associations, memberships, interest groups

## Description
The `guilds` table defines high-level associations or industry groups that stores can belong to. Unlike individual store-level settings, guilds represent a global grouping mechanism (likely for franchise networks, industry consortiums, or specialized trade groups). This classification allows the ERP to apply logic or share data across a collection of related but independent businesses. Examples of actual values include `Jack of All Trades` and `Power emergency`.

## ⚠️ SQL-Critical Behaviors
- **Global Scope**: Guilds are not scoped to a specific `store_id`. They are system-wide entities that any store can be associated with through the `stores_guilds` junction table.
- **Member Isolation**: While the guild definition is global, the data within the member stores remains isolated unless specific sharing rules are established at the guild level.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| name | text | no | — | Human-readable guild name. Examples of actual values include: `Jack of All Trades`, `Power emergency`. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| creator_id | uuid | no | — | The user who registered this guild. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| stores_guilds | guild_id | Junction table linking stores to this guild. |
| guilds_categories | guild_id | Defines which product categories are associated with this guild. |

## Common Query Patterns
```sql
-- Find all guilds currently active in the system
SELECT name FROM guilds WHERE is_active = true;

-- Find which guild a specific store belongs to
SELECT g.name 
FROM guilds g
JOIN stores_guilds sg ON g.id = sg.guild_id
WHERE sg.store_id = '<store_uuid>';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| is_active | btree | Filtering for active guilds. |
| name | btree | Searching/Filtering by guild name. |


