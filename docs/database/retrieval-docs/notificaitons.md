# notificaitons

## Purpose
The system alert registry for in-app messaging and broadcast updates. It serves as the master ledger for alerts, push notifications, and company-wide announcements, tracking content and action links for server-generated events.

---

## Retrieve This Table When The User Asks About

**System alerts and push notifications**
Alerts, bell icons, or popup messages. Finding the content (title/text) of a specific system notification or company-wide announcement.

**Job progress and technical failures**
Identifying long-running jobs (progress bars) or critical failure alerts (is_error). Finding the redirect path or URLs provided to resolve an alert.

**Notification targeting and audience**
Identifying alerts scoped to a specific branch (STORE), a single user, or every user in the system (GLOBAL).

---

## Co-Retrieved Sibling Tables
- `notificaiton_user` — the tracking of delivery and "seen" status for individual users.
- `stores` — the branch targeted by store-scoped alerts.
