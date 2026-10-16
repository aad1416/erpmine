# Gmail API adapter

Receives Mailboxes' mail through the Gmail API with an OAuth refresh token, and replies in the customer's thread. One `GmailAdapter` instance serves every Mailbox in `gmail_mailboxes`, each read by its own loop, so one Mailbox failing (a revoked token, a watch error, an API error) never stops the others. It runs beside the IMAP/SMTP adapter (ADR 0002). The Mailbox Registry refuses to start when an address is in both `gmail_mailboxes` and `imap_mailboxes`.

How it reads, hands messages over through its own outbox (`gmail_outbox`), and sends replies once per idempotency key is described at the top of `adapter.py`.

## Tables

| Table | What it holds |
|---|---|
| `gmail_mailboxes` | One row per Mailbox, keyed by address: store owner, enabled flag, encrypted refresh token, and `history_id` cursor. |
| `gmail_outbox` | Messages captured but not yet handed to ingestion, and delivered ones until `SUPPORT_RETENTION_DAYS`. |
| `gmail_sent_replies` | One row per reply by idempotency key: `sending`, then `sent`. |
| `gmail_watches` | Each push-mode Mailbox's last users.watch(): its historyId and expiry. |

## Settings (`SUPPORT_GMAIL_*`, `settings.py`)

| Setting | Default | |
|---|---|---|
| `SUPPORT_GMAIL_CLIENT_ID`, `SUPPORT_GMAIL_CLIENT_SECRET` | none | The app's OAuth client, shared by every Mailbox. Without both, no Mailbox is served. |
| `SUPPORT_GMAIL_DETECTION_MODE` | `poll` | `poll` or `push`. |
| `SUPPORT_GMAIL_POLL_INTERVAL_SECONDS` | 60 | Poll mode's read interval. |
| `SUPPORT_GMAIL_BACKUP_POLL_INTERVAL_SECONDS` | 900 | Push mode's backup read, for a dropped notification. |
| `SUPPORT_GMAIL_PUBSUB_TOPIC` | none | Push mode: the topic each Mailbox's watch publishes to. |
| `SUPPORT_GMAIL_PUBSUB_AUDIENCE` | none | Push mode: the audience the webhook checks Pub/Sub's token against. Unset, the token isn't checked. |
| `SUPPORT_GMAIL_WATCH_RENEWAL_INTERVAL_SECONDS` | 86400 | How often each watch is renewed. A watch expires after 7 days. |
| `SUPPORT_GMAIL_TIMEOUT_SECONDS` | 30 | Bounds each Gmail API request. |

The old names (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_DETECTION_MODE`, `GMAIL_POLL_INTERVAL_SECONDS`, `GMAIL_PUBSUB_TOPIC`, `GMAIL_PUBSUB_AUDIENCE`) are no longer read. Rename them to their `SUPPORT_GMAIL_*` names: in particular, without `SUPPORT_GMAIL_PUBSUB_AUDIENCE` the webhook doesn't check Pub/Sub's token.

## Admin mailbox API

Apply migrations and set `SUPPORT_CREDENTIALS_KEY`, `SUPPORT_GMAIL_CLIENT_ID`, and `SUPPORT_GMAIL_CLIENT_SECRET` on the server. The OAuth client settings are shared; each mailbox's refresh token is saved encrypted in SQLite.

With an admin bearer token, call `POST /support/mailboxes/gmail` with `{"mailbox":"help@example.com","refresh_token":"..."}`. The address is normalized to lowercase. The API checks that the refresh token grants access to that Gmail address before saving it; the same check runs when the token is replaced. The response is `201` and includes the address, `enabled`, `has_refresh_token`, and activation status, never the token. `GET /support/mailboxes/gmail` lists only mailboxes belonging to the admin's `storeId`; `GET /support/mailboxes/gmail/{mailbox}` reads one. `PUT /support/mailboxes/gmail/{mailbox}` accepts a replacement `refresh_token` and/or `enabled` (`true` or `false`). Omitted fields keep their values; explicit `null` is rejected. Changes are applied to the running adapter without a restart. Disabling waits for any reply already in progress, then stops reads and replies; enabling resumes from the saved cursor.

`POST /support/mailboxes/gmail/{mailbox}/disconnect` stops the mailbox and clears its saved refresh token. The mailbox row, owner, cursor, and support history remain. This removes the app's saved authorization; it does not revoke the OAuth grant at Google. To reconnect it, call `PUT /support/mailboxes/gmail/{mailbox}` with a new `refresh_token` and `enabled: true`. Enabling without a token returns `422`. Mutating requests return `503` without saving when the live support adapter is unavailable.

Previously seeded Gmail rows have no store owner. An admin can claim one by posting its address and **the same saved refresh token** to the create endpoint; this returns `200` and preserves its cursor. A migrated row with no token can be claimed with a new token. An incorrect token on an already configured row returns `409`. The legacy seed script remains available for migration, but new accounts need no seed step. Do not rerun the legacy seeder after moving an account to API management because it can replace the token from old environment variables.

A Mailbox without a cursor starts from now: mail from before its first read is not ingested.

## Push mode

The Pub/Sub push subscription's endpoint is `POST /support/webhooks/gmail`, served by the adapter's `router()`. A notification wakes that Mailbox's read and is answered 204 at once. The route is only mounted while Support Email runs (`SUPPORT_ENABLED`).
