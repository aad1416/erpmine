# notificaiton_user

## Purpose
The user-delivery junction for system alerts. It records exactly which users were targeted by a specific notification and tracks the "Seen/Unseen" status independently for each person to manage their application dashboard feeds.

---

## Retrieve This Table When The User Asks About

**User alerts and inbox logs**
Notification status or message delivery tracking. Calculating the "Unread Count" for a specific user's dashboard.

**Read status and interaction**
Finding which staff members have physically interacted with or viewed a specific system alert. Auditing the delivery history for a broadcast message.

---

## Co-Retrieved Sibling Tables
- `notificaitons` — the master system alert.
- `users` — the staff member receiving the message.
