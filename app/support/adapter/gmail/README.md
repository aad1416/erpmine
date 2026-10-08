# Gmail API adapter

Receives Mailboxes' mail through the Gmail API with an OAuth refresh token, and replies in the customer's thread. One `GmailAdapter` instance serves every Mailbox in `gmail_mailboxes`, each read by its own loop, so one Mailbox failing (a revoked token, a watch error, an API error) never stops the others. It runs beside the IMAP/SMTP adapter (ADR 0002). The Mailbox Registry refuses to start when an address is in both `gmail_mailboxes` and `imap_mailboxes`.

How it reads, hands messages over through its own outbox (`gmail_outbox`), and sends replies once per idempotency key is described at the top of `adapter.py`.

## Tables

| Table | What it holds |
|---|---|
| `gmail_mailboxes` | One row per Mailbox, keyed by address: the encrypted refresh token and `history_id`, the cursor. |
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

## Adding a Mailbox

1. Set `GMAIL_USER_EMAIL` and `GMAIL_REFRESH_TOKEN` in the env, and `SUPPORT_CREDENTIALS_KEY`. Only the seed script reads the first two (`GmailSeedSettings` in `seed.py`); the app reads the table.
2. Run `poetry run python scripts/seed_support_mailboxes.py`. It copies them into `gmail_mailboxes`, encrypting the token, and prints only the address.
3. Restart the app.

A Mailbox without a cursor starts from now: mail from before its first read is not ingested.

## Push mode

The Pub/Sub push subscription's endpoint is `POST /support/webhooks/gmail`, served by the adapter's `router()`. A notification wakes that Mailbox's read and is answered 204 at once. The route is only mounted while Support Email runs (`SUPPORT_ENABLED`).
