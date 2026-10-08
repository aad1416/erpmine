# `news_letter_view_reports`

## Searchable Aliases
newsletter analytics, open rates, engagement logs, marketing report, view tracking

## Description
The `news_letter_view_reports` table is the **Engagement Analytics Ledger** for the **Lyndom** (the current PostgreSQL ERP) mass-communication domain. It tracks the specific delivery status and interaction history for every recipient targeted by a newsletter campaign.

By recording "Opens," "Views," and "Total Interaction Counts," this table provides the business with the data required to measure campaign effectiveness, identify non-responsive clients, and manage re-delivery workflows.

## ⚙️ The Engagement Tracking Workflow
1.  **Issuance Logging**: When a newsletter is sent, a record is created here for every recipient, capturing their `email` and the `sent_at` timestamp.
2.  **The "Open" Event**: When the recipient opens the email (typically via a tracking pixel), the system updates the `seen` boolean to `true` and records the `seen_at` timestamp.
3.  **Detailed Auditing**: Every subsequent time the email is viewed, the `total_views` counter is incremented, and the detailed event (IP, user-agent, or timestamp) is appended to the `views` JSONB object.
4.  **Resend Management**: If a recipient hasn't opened the email after a certain period, administrative users can trigger a follow-up, incrementing the `resend_count`.

## ⚠️ SQL-Critical Behaviors
- **Complex Event Storage**: The `views` JSONB field is the "Interaction Chronicle." It allows for deep forensic analysis of how a specific client interacted with the content over time.
- **Recipient Diversity**: The table connects to both **Resellers** (`rep_id` links to `clients`) and **Direct Contacts** (`contact_id` links to `contacts`).
- **Performance Analytics**: The delta between `sent_at` and `seen_at` provides critical data for optimizing future communication schedules (identifying the "Best Time to Send").

## Columns (14 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that launched the campaign. |
| newsletter_id | uuid | no | — | Link to the parent campaign in `news_letters.id`. |
| rep_id | uuid | yes | — | **Reseller Link**: Link to the client record in `clients.id` (if acting as a rep). |
| contact_id | uuid | yes | — | **Contact Link**: Link to the individual in `contacts.id`. |
| email | text | no | — | The specific destination email address. |
| sent_at | int8 | no | — | The timestamp the message left the ERP server (Epoch). |
| seen_at | int8 | yes | — | The timestamp of the **first** open event (Epoch). |
| seen | bool | no | false | **Interaction Toggle**: If `true`, the email has been opened at least once. |
| resend_count | int4 | no | 0 | Count of how many times this specific message was re-sent to the user. |
| total_views | int4 | no | 0 | The cumulative count of all "Open" events for this record. |
| views | jsonb | no | — | **Detailed Interaction Log**: JSON array of viewing events and metadata. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| newsletter_id | news_letters | id | cascade |
| rep_id | clients | id | cascade |
| contact_id | contacts | id | cascade |

## Common Query Patterns
```sql
-- Calculate the "Open Rate" for a specific newsletter campaign
SELECT 
  (COUNT(NULLIF(seen, false))::float / COUNT(id)::float) * 100 as open_rate_percent
FROM news_letter_view_reports 
WHERE newsletter_id = '<newsletter_uuid>';

-- List the most engaged recipients (those who viewed the email 5+ times)
SELECT email, total_views 
FROM news_letter_view_reports 
WHERE total_views >= 5 
ORDER BY total_views DESC;
```

## Indexes
- *Relies on standard relational indexes on `newsletter_id` and `email` for campaign analytics reporting.*
