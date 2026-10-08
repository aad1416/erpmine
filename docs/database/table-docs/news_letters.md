# `news_letters`

## Searchable Aliases
email campaigns, newsletters, marketing blasts, subscriber updates, announcements

## Description
The `news_letters` table is the **Mass-Communication Command Center** for the **Lyndom** (the current PostgreSQL ERP) system. It manages the content and metadata for broadcast email campaigns, including newsletters, promotional announcements, and system-wide bulletins.

While `notifications` are for targeted system events, `news_letters` are for proactive, high-volume outbound messaging. This table serves as the primary "Drafting Board" for marketing and administrative communications.

## ⚙️ The Campaign Dispatch Workflow
1.  **Drafting**: A user (Marketing or Admin) creates a `news_letters` record, defining the internal `title` and the public email `subject`.
2.  **Content Design**: The HTML or text `content` is recorded.
3.  **Attachment Pairing**: Any supplemental documents (e.g., PDF catalog updates) are linked via the `news_letter_files` junction.
4.  **Scheduled Release**: The `date` field identifies when the message is authoritative or scheduled for delivery.
5.  **Analytics Tracking**: Once sent, the delivery results are tracked in the `news_letter_view_reports` table to measure engagement.

## ⚠️ SQL-Critical Behaviors
- **Subject vs. Title**: The system separates the "Email Subject Line" (`subject`) from the "Internal Management Name" (`title`). This allows for organization (e.g., "Monthly Promo - May") to exist alongside a marketing hook (e.g., "Exclusive 20% Off Your Next Build!").
- **Tenant Isolation**: Newsletters are strictly partitioned by `store_id`, ensuring that branch-specific marketing stays within its designated regional audience.
- **Creator Audit**: The `creator_id` ensures that all mass-comms can be traced back to the authorized user who designed the campaign.

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the campaign. |
| subject | text | yes | — | **Public Subject Line**: The text the customer sees in their inbox. |
| title | text | no | — | **Internal Name**: The descriptive name used in the ERP dashboard. |
| content | text | no | — | **The Message Body**: The actual text/HTML content of the newsletter. |
| is_active | bool | no | true | Status flag. If `false`, the campaign is retired. |
| creator_id | uuid | no | — | The marketing/admin user who designed the campaign. |
| date | int8 | no | — | The scheduled or reference date for the campaign (Epoch). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| news_letter_files | newsletter_id | Attachment links for this campaign. |
| news_letter_view_reports | newsletter_id | The analytics/delivery report for this campaign. |

## Common Query Patterns
```sql
-- List all active campaigns for the current store
SELECT title, date 
FROM news_letters 
WHERE store_id = '<uuid>' AND is_active = true 
ORDER BY date DESC;

-- Identify campaigns created by a specific user in the last quarter
SELECT title, subject 
FROM news_letters 
WHERE creator_id = '<user_uuid>' 
  AND created_at > (NOW() - INTERVAL '90 days');
```

## Indexes
- *Uses standard relational indexes on `store_id` and `creator_id` for management auditing.*
