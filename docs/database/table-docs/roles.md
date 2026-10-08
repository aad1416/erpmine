# `roles`

## Searchable Aliases
permissions, access levels, user groups, security profiles, authorization, privileges, job titles, technicians, managers

## Description
The `roles` table is the hub for Role-Based Access Control (RBAC) in the system. It defines reusable sets of permissions (stored in the `accesses` JSONB blob) that can be assigned to users. This abstraction allows for scalable security management where, instead of assigning hundreds of permissions to each user individually, they are assigned a role like "Warehouse Manager" or "Field Technician". Roles can be defined globally (available to all locations) or locally (scoped to a specific `store_id`). This table also identifies "protected" system roles that are critical for operation and restricted from modification or deletion.

## ⚠️ SQL-Critical Behaviors
- **JSONB Permissions**: The `accesses` column is a **JSONB Array of strings**. These strings represent permission keys (e.g., `"ITEM_STORE_EDIT_STORE_PANEL"`, `"CATEGORY_DELETE_MGMT"`). 
- **Array Querying**: To check for a permission, use the PostgreSQL JSONB containment operator `@>` with an array literal.
- **Protected Status**: If `protected = true`, the record is a system-default role and should typically be treated as read-only.
- **Global vs. Local**: A `NULL` `store_id` indicates a global role, while a populated `store_id` indicates a custom role specific to that branch.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | yes | — | The store this role belongs to (NULL for global roles). |
| name | text | no | — | Human-readable name of the role. |
| accesses | jsonb | no | — | ⚠️ **String Array**. Contains strings like `"ITEM_STORE_EDIT_STORE_PANEL"` and `"CATEGORY_DELETE_MGMT"`. |
| type | role_type_enum | no | — | Scope of the role. Values: `MANAGEMENT`, `STORE`. |
| protected | bool | no | — | Indicates if the role is a system-critical default and cannot be deleted. |
| creator_id | uuid | no | — | The user who created this role definition. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| users_roles | role_entity_id | Junction table mapping this role to specific users. |

## Role Profiles and Custom Roles
Roles in this system are **dynamic**. Authorized administrators (e.g., those possessing `ROLE_CREATE_MGMT` access) can dynamically create, modify, and delete unprotected roles. However, the system relies on certain default **protected** roles that cannot be deleted:
- **`Manager Full Access`**: A global management role (`type = 'MANAGEMENT'`, `protected = true`). Contains all global `_MGMT` accesses.
- **`Store Owner`**: A local branch operations role (`type = 'STORE'`, `protected = true`). Contains all local `_STORE_PANEL` accesses. (Note: there is a distinct `Store Owner` role record duplicated for every physical store).

- **Unprotected Roles**: Any role with `protected = false` (such as hypothetical custom roles like `Inventor`, `Warehouse Staff`, or `Custom Role A`) can be fully managed by authorized admins. These unprotected roles can contain any arbitrary subset of the 569 system-wide access keys.
- **Additive Security Model**: A user's total permissions are the **union** of all roles assigned to them via the `users_roles` junction table. Users frequently hold multiple roles (e.g., Manager Full Access + Store Owner for a specific branch) to combine global and local capabilities.

## Access Key Naming Convention
If you are asked about user capabilities, authorizations, or permissions (e.g., "who can edit quotes?"), you must check the `accesses` JSONB array. The keys follow a strict pattern:
    `{ENTITY}_{ACTION}_{SCOPE}`
- **SCOPE**: Either `MGMT` (global management) or `STORE_PANEL` (local branch operations).
- **ACTION**: Common verbs: `CREATE`, `READ`, `EDIT`, `DELETE`, `ACTIVATE`, `DEACTIVATE`, `IMPORT`, `CANCEL`, `ACKNOWLEDGE`, `SHIP`, `DELIVER`.
- **ENTITY**: The business domain object. Examples: `ITEM`, `PURCHASE_ORDER`, `SALES_ORDER`, `QUOTE`, `VENDOR`, `CLIENT`, `SHIPMENT`, `BOM`, `RMA`, `INVENTORY_ITEM`, `ROLE`, `USER`, `CATEGORY`, `SPECIFICATION`, `FIELD_SERVICE_TICKET`.
To construct a key from natural language: "can create purchase orders at store level" → `PURCHASE_ORDER_CREATE_STORE_PANEL`. "can edit store items at the store level" → `ITEM_STORE_EDIT_STORE_PANEL`.

*Note: While 81% of keys strictly follow the `{ENTITY}_{ACTION}_{SCOPE}` formula, specialized operations (~18%) utilize custom actions or invert the prefix order (e.g., `{ACTION}_{ENTITY}`). Other custom verbs you may encounter include: `ARCHIVE`/`UNARCHIVE`, `ASSIGN`/`UNASSIGN`, `HOLD`/`UNHOLD`, `CHECK`/`UNCHECK`, `REJECT`, `REVERT`, `RETURN`, `RESOLVE`, `ACCEPT`, `CONVERT`, `UNDO`, `DISABLE`, `SEEN`, or multi-word actions like `ADD_TO_STAGE`, `SET_AS_CURRENT`, `UPLOAD_FILE`.*

## Common Query Patterns
```sql
-- 1. Comprehensive capability lookup: Find active users who can CREATE but CANNOT DELETE items at a specific branch
SELECT DISTINCT u.full_name, s.name AS branch_name
FROM users u
JOIN users_roles ur ON u.id = ur.user_entity_id
JOIN roles r ON r.id = ur.role_entity_id
JOIN stores s ON r.store_id = s.id
WHERE u.is_active = true
  AND r.accesses @> '["ITEM_CREATE_STORE_PANEL"]'
  AND NOT (r.accesses @> '["ITEM_DELETE_STORE_PANEL"]')
  AND s.name = 'DSPM';

-- 2. Correctly count active users per role (INNER JOIN prevents returning roles with 0 users)
SELECT r.name, COUNT(DISTINCT u.id) AS active_user_count
FROM roles r
INNER JOIN users_roles ur ON r.id = ur.role_entity_id
INNER JOIN users u ON u.id = ur.user_entity_id AND u.is_active = true
GROUP BY r.name ORDER BY active_user_count DESC;

-- 3. Join business transactions to a specific role (Role name is NOT user full_name)
SELECT q.number
FROM quotes q
JOIN users u ON q.creator_id = u.id
JOIN users_roles ur ON u.id = ur.user_entity_id
JOIN roles r ON r.id = ur.role_entity_id
WHERE r.name = 'Manager Full Access' AND q.status != 'SOLD';

-- 4. Count total permissions assigned to each role definition
SELECT name, jsonb_array_length(accesses) AS permission_count
FROM roles WHERE is_active = true ORDER BY permission_count DESC;
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting roles by creation order. |
| name | btree | Fast lookup for role selection. |
| protected | btree | Identifying system-protected roles for safety checks. |
| type | btree | Finding roles within a specific organizational level. |


