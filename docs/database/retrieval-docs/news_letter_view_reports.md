# news_letter_view_reports

## Purpose
The engagement analytics ledger. It tracks the delivery status and interaction history—including opens and total views—for every recipient of a newsletter campaign to measure marketing effectiveness.

---

## Retrieve This Table When The User Asks About

**Newsletter analytics and open rates**
Engagement logs or marketing reports. Calculating the open-rate percentage for a specific campaign.

**Recipient interaction and tracking**
Identifying the most engaged recipients (those with 5+ views). Auditing the first "Seen" event vs. the initial "Sent" timestamp to optimize delivery schedules.

**Analytics forensics**
Retrieving detailed interaction logs (JSON) to analyze how specific clients interacted with campaign content over time. Checking the resend count for non-responsive contacts.

---

## Co-Retrieved Sibling Tables
- `news_letters` — the parent marketing campaign.
- `contacts` — the individual recipient.
- `clients` — the reseller or company receiving the update.
