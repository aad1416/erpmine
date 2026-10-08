# `notificaiton_user`

## Searchable Aliases
user alerts, notification status, message delivery tracking, inbox logs

> [!NOTE]
> **Schema Naming Note**: While the parent table is misspelled as `notificaitons`, the foreign key in this table is spelled **`notification_id`**.

## Description
The `notificaiton_user` table is the **User-Delivery Junction** for system alerts. It records exactly which users have been targeted by a specific notification and, more importantly, whether they have physically "seen" the message in their application dashboard.

This table allows the ERP to broadcast a single notification (e.g., a "Public Holiday Store Closure" notice) to every employee in a store simultaneously, while tracking the "Seen/Unseen" status independently for each individual person.

## ⚙️ The Notification Consumption Workflow
1.  **Audience Filtering**: When a notification is created, the system identifies the targeted individuals (e.g., all users with the "Warehouse Manager" role).
2.  **Delivery Insertion**: A record is created in this table for every targeted `user_id`, linked to the `notification_id`.
3.  **UI Feedback**: In the application dashboard, the system queries this table for all records where `seen = false` to generate the "Unread Notification" counter.
4.  **Interaction**: When the user clicks on the notification, the system updates the `seen` flag to `true`, clearing the counter.

## ⚠️ SQL-Critical Behaviors
- **Decoupled Read Status**: By using this junction, the parent notification can remain "Active" for weeks, while it disappears from individual user feeds once it is marked as `seen`.
- **High-Performance Querying**: This table is queried on every page load to populate the global "Bell" icon count.
- **Relational Integrity**: Deleting a master notification from the `notificaitons` table will automatically purge all associated delivery records here.

## Columns (6 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| notification_id | uuid | no | — | Link to the master alert in `notificaitons.id`. |
| user_id | uuid | no | — | **The Recipient**: Link to the target employee in `users.id`. |
| seen | bool | no | false | **Read Status**: If `true`, the user has interacted with/viewed the alert. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| notification_id | notificaitons | id | cascade |
| user_id | users | id | cascade |

## Common Query Patterns
```sql
-- Calculate the "Unread Count" for a specific user's dashboard
SELECT COUNT(id) 
FROM notificaiton_user 
WHERE user_id = '<uuid>' AND seen = false;

-- Mark all notifications for a specific user as "Seen"
UPDATE notificaiton_user 
SET seen = true 
WHERE user_id = '<uuid>';
```

## Indexes
- *Relies on standard relational indexes on `user_id` and `notification_id` for UI feed generation.*
