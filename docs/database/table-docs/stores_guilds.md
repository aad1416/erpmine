# `stores_guilds`

## Searchable Aliases
store membership, branch community links, industry associations

## Description
The `stores_guilds` table is a many-to-many junction that assigns stores/branches to specific guilds. By linking a `store.id` to a `guild.id`, the system establishes membership in industry groups or franchise networks. This allows for cumulative membership where a single branch can belong to multiple guilds simultaneously (e.g., a "Power Emergency" guild for specialized equipment and a "Jack of All Trades" guild for general hardware). 

## ⚠️ SQL-Critical Behaviors
- **Membership Junction**: This is the only way to determine guild membership. To find which stores belong to which guilds, you must join `stores` -> `stores_guilds` -> `guilds`.
- **Composite Primary Key**: This table uses the combination of `(store_entity_id, guild_entity_id)` as its primary key to ensure a store cannot be joined to the same guild multiple times.
- **Cascading Deletion**: If a store or a guild is deleted, its associated membership records in this table are automatically removed.

## Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| store_entity_id | uuid | no | Foreign key to `stores.id`. |
| guild_entity_id | uuid | no | Foreign key to `guilds.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_entity_id | stores | id | cascade |
| guild_entity_id | guilds | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all stores belonging to a specific guild
SELECT s.name 
FROM stores s
JOIN stores_guilds sg ON s.id = sg.store_entity_id
JOIN guilds g ON g.id = sg.guild_entity_id
WHERE g.name = 'Jack of All Trades';

-- Count how many stores are in each guild
SELECT g.name, COUNT(sg.store_entity_id) 
FROM guilds g
LEFT JOIN stores_guilds sg ON g.id = sg.guild_entity_id
GROUP BY g.name;
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| (store_entity_id, guild_entity_id) | btree (PK) | Ensures uniqueness and optimizes join performance. |


