# IMAP Mailbox Adapter

Receives Mailboxes' mail over IMAP with an app password (ADR 0002), beside the Gmail API adapter, and replies over SMTP in the customer's existing thread. One `ImapAdapter` instance serves every Mailbox in `imap_mailboxes`, each polled by its own loop. Works with Gmail and with any other Mail Provider (Yahoo, Fastmail, iCloud, Zoho, self-hosted); see [Gmail and other Mail Providers](#gmail-and-other-mail-providers).

## Configuration

Each Mailbox is a row of `imap_mailboxes` (`models.ImapMailbox`), keyed by its lower-cased address and owned by one required, unique `store_id`. The adapter serves every row with an app password at startup. Saving settings also activates the saved connection in the running adapter, without an app restart. Creating a mailbox starts at its current inbox position; changing an existing mailbox address replays mail received in the new inbox since the change request began.

An admin token with a nonempty `storeId` claim can create or partially update the store's connection with `PUT /support/mailboxes/imap` and read it with `GET /support/mailboxes/imap` while `SUPPORT_ENABLED=true`. The first PUT requires `mailbox` and `app_password`; all six host, port, and TLS settings are optional and use Gmail defaults. A later PUT changes any supplied connection fields and retains omitted values, including the encrypted password. Explicit `null` is invalid. Creation returns 201; updates return 200. Both return `restart_required: false`, `activation_status` (`active`, `activating`, `failed`, or `unavailable`), a safe `activation_error` when applicable, and `transition` for an address change. They never include the app password or polling cursor. Changing non-address fields preserves the cursor. An address already configured for another store or adapter returns 409. A completed transition reserves its retired address for the original store so historical support records stay store-scoped.

For a live PUT, the adapter checks the proposed IMAP login and reads the new INBOX's UID watermark with STATUS before recording a waiting transition or selecting that inbox. A failed check returns 422 and leaves the saved connection and cursor intact; the pending transition and its safe error appear in GET. Retry the same PUT after correcting the settings or connectivity. On success, the old poller finishes its current step and stops, then one replacement starts. Sends that acquire the old connection before the switch finish with its SMTP settings before the replacement is saved. Once the switch holds the send lock, queued sends recheck the active connection: a same-address change uses the new SMTP settings. An address change returns 409 while the old address has open or running support tasks or captured messages awaiting ingestion. The 409 response and GET include counts, `needs_attention`, and an action. Queued replies can finish before the switch. A dead-letter reply does not block forever: after the switch it remains visible under the old address in support monitoring, and the transition shows the count and manual recovery action. A reply interrupted mid-send has an unconfirmed outcome; the transition shows its count and asks the admin to check the Sent folder before contacting the customer. `POST /support/mailboxes/imap/transition/cancel` abandons a waiting change without changing the active connection. `POST /support/mailboxes/imap/retry` retries an already saved connection that failed at startup or later lost its login. A rejected login stops that mailbox's poller and is visible through GET. Temporary poll failures are visible while the poller continues its normal retries. SMTP delivery is attempted when a customer reply is sent; `active` confirms IMAP polling, not SMTP delivery.

On the first address-change request, `imap_address_transitions` stores the UTC request time for the date scan. Repeated PUTs for the same old and new addresses reuse it, including after a failed login or app restart. The adapter searches the new INBOX by IMAP `INTERNALDATE` from that time. Before recording a successful first transition, it reads `UIDVALIDITY` and `UIDNEXT` with STATUS and saves those values and the server endpoint. Mail appended after that watermark, including during the first SELECT, has a UID at or above it even if `INTERNALDATE` is older. On retry, the cursor starts before the earlier of the date match and that saved UID. If the UID namespace changes, it scans the new inbox from the beginning to avoid skipping mail. This can ingest older messages that were already present there. The date scan includes the entire first second because IMAP records delivery to the second. The checkpoint scan fetches dates only; normal polling fetches message bodies. The mailbox cursor and `imap_outbox` handoff prevent repeated delivery on retry or restart. If two addresses reach the same physical inbox, an old-address outbox row also prevents the new poller from delivering that message twice. Apply migrations through `f9c0d1e2a3b4` before using this flow.

This branch includes the email-attachment migration `d6f8a93e12b4` because the IMAP transition migration `d7a8b9c0d1e2` follows it in the current Alembic chain. The attachment schema belongs to the earlier email-attachment work; keep that dependency visible when merging or rebasing this branch.

Before the first STATUS response, the request has no UID checkpoint. The date cutoff cannot reliably identify messages copied into the new inbox with an older `INTERNALDATE` during that interval, even when the connection succeeds. Every new address transition therefore keeps `backfill_review_required` visible after activation. The frontend shows a confirmation modal covering the pre-checkpoint inbox review and any dead-letter or unconfirmed old-mailbox replies. After the admin confirms that these have been handled, `POST /support/mailboxes/imap/transition/backfill-reviewed` acknowledges the completed transition. A nullable `reviewed_at` on that transition distinguishes confirmation from older transitions whose backfill flag was already false. Its response and later GETs return `backfill_review_required: false`, `needs_attention: false`, and `action: ""`. Reply counts still report the actual dead-letter and unconfirmed records. The original task and send records remain unchanged for audit; acknowledgement does not prove that an uncertain reply was delivered.

An address change while the support adapter is unavailable returns 503 and leaves the saved address unchanged, because queued replies cannot be drained safely without the running adapter. Initial mailbox setup can still be saved while the adapter is unavailable.

| Column | Default | Notes |
|---|---|---|
| `mailbox` | | the Mailbox address |
| `store_id` | | required and unique; taken from the admin token for settings routes |
| `app_password` | | encrypted with `SUPPORT_CREDENTIALS_KEY`. For Gmail a Google app password (needs 2-Step Verification); other Mail Providers issue their own. A row without one is logged and not served |
| `imap_host` / `imap_port` / `imap_tls_mode` | `imap.gmail.com` / `993` / `ssl` | set all three for a non-Gmail Mail Provider; TLS mode is `ssl` or `starttls` |
| `smtp_host` / `smtp_port` / `smtp_tls_mode` | `smtp.gmail.com` / `465` / `ssl` | for replies; logs in with the same app password |
| `cursor` | | `<uidvalidity>:<last_uid>`, owned by the adapter |

`scripts/seed_support_mailboxes.py` copies the env-configured Mailbox into the table (`seed.py`): `IMAP_MAILBOX_STORE_ID`, `IMAP_MAILBOX_EMAIL`, `IMAP_MAILBOX_APP_PASSWORD`, and `IMAP_HOST` / `IMAP_PORT` / `IMAP_TLS_MODE` / `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS_MODE`, with Gmail's servers for any left unset. `IMAP_MAILBOX_STORE_ID` is required when seeding an IMAP address. Only the seed script reads these variables (`ImapSeedSettings`); the app reads the table. It never prints the app password and leaves the cursor alone. The seed script rejects reassignment of an active or retired IMAP address to another store, preserving access to historical support records.

| Setting | Default | Notes |
|---|---|---|
| `SUPPORT_IMAP_POLL_INTERVAL_SECONDS` | `60` | how often each Mailbox is polled |
| `SUPPORT_IMAP_TIMEOUT_SECONDS` | `30` | bounds each IMAP step and each SMTP send |

## Gmail and other Mail Providers

Each poll checks whether the server offers Gmail's `X-GM-EXT-1` extension.

| | With `X-GM-EXT-1` (Gmail) | Without it (any other server) |
|---|---|---|
| External message ID | `X-GM-MSGID` in hex, equal to the Gmail API's `id` | the `Message-ID` header, e.g. `<abc@example.com>`; if missing, `sha256:<hex>` of the From, To, Cc, Date, Subject, In-Reply-To and References headers |
| Conversation ID | `X-GM-THRID` in hex, equal to the Gmail API's `threadId` | the Conversation of the message it answers, else a new one: the first 32 hex digits of SHA-256 of its external message ID |
| Sent and draft mail | skipped by `\Sent` / `\Draft` label, or From | skipped by From (no labels) |

Without Gmail's extensions, a message answers a Conversation when its `In-Reply-To`, or any of its `References` (newest first), is a Message-ID in `imap_thread_messages`: an inbound message or a reply we sent. Otherwise it starts a new Conversation. Subjects are never matched, so a fresh email titled "Re: Order #1001" is a new Conversation.

A message without a Message-ID is captured once however often it is fetched, because its hashed ID is stable. Two such messages with the same key headers (sender, recipients, date to the second, subject) are taken for one. A reply to it reaches the customer but can't set `In-Reply-To`, so their client may show it as a new thread.

Replies on other Mail Providers are sent over their SMTP server just as on Gmail. We don't append a copy to the Mailbox's Sent folder, and not every provider files SMTP mail there itself as Gmail does.

## Mail that is not from a customer

Only customer mail is captured (`filters.py`). Skipped, in this order:
- labelled `\Draft` or `\Sent` (the Mailbox is used only by this app, so sent mail is ours; Gmail only);
- From the Mailbox's own address (works without labels, for non-Gmail servers);
- bounces: empty `Return-Path`, a `mailer-daemon` or `postmaster` sender, or a delivery-status report. Logged at WARNING with the Mailbox and the bounced mail's Message-ID when the report carries it;
- auto-replies: `Auto-Submitted` other than `no`, `X-Autoreply`, or `Precedence: bulk | auto_reply | junk`.

Our own replies (by Message-ID, below) are skipped too. A skipped message is marked read and never captured, and the cursor moves past it.

## Handing messages to ingestion

The adapter keeps its own outbox, `imap_outbox`. For each new customer message:
1. in one transaction, the message is written to the outbox as captured and the cursor moves past it;
2. it is marked read on the server;
3. it is handed to the sink;
4. its outbox row is marked delivered.

A crash before step 1 leaves the message unread and before the cursor, so the next poll fetches it again. A crash after step 1 leaves an undelivered row: on start the adapter re-sinks every undelivered row before it polls, and each poll re-sinks its Mailbox's undelivered rows first, which also retries a sink that failed. The sink ignores a message it already has, so a re-sink never makes a second task. Delivered rows are purged after `SUPPORT_RETENTION_DAYS`, except for addresses involved in a waiting or completed change. Those rows become payload-free `tombstone` records after retention; their message IDs prevent duplicate ingestion even if the replacement inbox replays late. A later poll also compacts retired addresses.

## Replies and threading

`imap_thread_messages` records, per Mailbox (`adapter` + `mailbox`), every inbound message's Message-ID, References, sender and Conversation (written at capture, before the outbox row), and every Message-ID we send. It is never purged, so a Conversation older than `SUPPORT_RETENTION_DAYS` still threads. Look a message up with `ImapThreadRepository.find_by_message_id`.

A reply:
- goes to the Conversation's last inbound sender only, never to CCs;
- sets `In-Reply-To` to that message's Message-ID, `References` to its References plus its Message-ID, and its subject with one `Re:`;
- gets a Message-ID we generate and record before sending, so if it ever comes back in through INBOX the fetch path skips it (and marks it read);
- is sent with aiosmtplib from the Mailbox address. No copy is appended to Sent: Gmail files it there itself;
- goes out from the Mailbox the reply task names, over that Mailbox's SMTP server;
- raises on any SMTP failure, so the send task goes to retry and dead-letter.

Each reply is sent once per idempotency key (the send task's ID), recorded in `imap_sent_replies`: as `sending` before SMTP, then `sent`. A retry of a `sent` key is skipped. A failed send removes its record, so the retry sends. A `sending` record left behind means an earlier attempt stopped between SMTP and recording the result (a crash, or the worker cancelled mid-send): the reply may or may not have reached the customer, so it is not sent again and a WARNING names the reply and its Message-ID. An SMTP error after the server already accepted the message (e.g. a timeout waiting for its answer) still counts as failed, so its retry can send the reply twice, as before.

## Staying up through failures

One broken message, a changed mailbox or a revoked app password never silently stops a Mailbox's mail, and never affects another Mailbox.

- **Backlog:** at most 200 messages per poll, oldest first. The rest come on the next poll.
- **Hung step:** every IMAP step (connect and each command) has a 30-second socket timeout. A timeout fails that poll, drops the connection, and the next poll reconnects. Connection and database errors never count against a message.
- **Oversized message:** over 40 MiB (by `RFC822.SIZE`, so the body is never downloaded) it is logged at WARNING and skipped. This allows for base64 expansion of the 25 MiB attachment limit.
- **Failing message:** a message that fails to capture (bad parse, missing Gmail IDs on Gmail) stops the poll there, so it is retried first next poll. On its 3rd failure in a row it is logged at ERROR and skipped. The count lives in the cursor, `<uidvalidity>:<last_uid>:<failing_uid>:<failures>`, so it survives restarts.
- Oversized and failed messages stay **unread** and in INBOX, so a person looking at the Mailbox still sees them.
- **UIDVALIDITY change:** old UIDs mean nothing, so the cursor restarts just before the first message of the last 3 days (IMAP `SINCE`). Mail already handed over is not handed over again: its `imap_outbox` row is found by `(mailbox, external_message_id)`, since message IDs (Gmail's, or from the headers) don't change; this relies on `SUPPORT_RETENTION_DAYS` staying above 3.
- **Login rejected** (e.g. a Google password change revoked the app password): logs an ERROR naming the Mailbox and stops polling it. The login is never retried automatically, so Google doesn't lock the account out. Saving a new app password activates it immediately; the retry endpoint also allows a manual retry.
- **Hung server:** each Mailbox polls in its own loop and its IMAP calls run off the event loop, so a server that stops answering holds up only its own Mailbox.
- **Same address in the Gmail API and IMAP**: a Mailbox uses exactly one Connection Method. The Mailbox Registry refuses to start when an address is in both `imap_mailboxes` and `gmail_mailboxes`.

## Manual check against a real Gmail Mailbox

The automated tests use a fake IMAP server. To check against Gmail itself:

1. On a test Google account with 2-Step Verification on, create an app password at <https://myaccount.google.com/apppasswords>.
2. Set these, run `poetry run python scripts/seed_support_mailboxes.py`, and start the app:
   ```
   SUPPORT_CREDENTIALS_KEY=<a Fernet key>
   IMAP_MAILBOX_STORE_ID=<store id>
   IMAP_MAILBOX_EMAIL=<test account>@gmail.com
   IMAP_MAILBOX_APP_PASSWORD=<app password>
   ```
3. Within a minute the log shows `IMAP Mailbox <email>: seeding cursor at <uidvalidity>:<uid>`. Nothing already in INBOX is ingested.
4. From another address, send an email to the Mailbox. Within a minute:
   - the log shows `IMAP Mailbox <email>: 1 new message(s)`;
   - a `conversations` row exists with `adapter = 'imap'` and `mailbox = '<email>'`;
   - in Gmail, the email is marked read and is still in the Inbox.
5. Compare IDs with the Gmail API. Open the email in Gmail, choose "Show original", and copy the Message-ID header. Then run [users.messages.list](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list) in the API Explorer with `q=rfc822msgid:<Message-ID>`. The returned `id` and `threadId` must equal the conversation message's `external_message_id` and the Conversation's `conversation_id`.
6. Restart the app. The next poll ingests nothing new and the `cursor` in the Mailbox's `imap_mailboxes` row does not change.
7. Let the AI reply to the email from step 4. Within a minute:
   - the log shows `IMAP Mailbox <email>: sent reply <message-id> in conversation <conversation_id>`;
   - the sender's mail client shows the reply inside the original thread, with `In-Reply-To` and `References` naming the original's Message-ID ("Show original" in Gmail);
   - the Mailbox's Sent folder holds exactly one copy, in the same Gmail thread;
   - an `imap_thread_messages` row with `direction = 'outbound'` holds the reply's Message-ID.
8. Reply to the AI's reply from the customer address. The next poll ingests it into the same Conversation, and never ingests the AI's reply itself.

## Manual check against another Mail Provider

The automated tests (`test_other_providers.py`) run the fake server without `X-GM-EXT-1`. To check against a real non-Gmail Mailbox, e.g. Fastmail (`imap.fastmail.com:993`, `smtp.fastmail.com:465`, both `ssl`) or Yahoo (`imap.mail.yahoo.com:993`, `smtp.mail.yahoo.com:465`):

1. Create an app password in the provider's security settings.
2. Seed the Mailbox as in step 2 above, adding all six `IMAP_*`/`SMTP_*` host, port and TLS settings, and start the app.
3. From another address, send an email to the Mailbox. Within a minute a `conversations` row exists with `adapter = 'imap'` and `mailbox = '<email>'`, and its conversation message's `external_message_id` is the email's Message-ID header.
4. Let the AI reply. The sender's client shows the reply in the original thread, with `In-Reply-To` naming the original's Message-ID.
5. Reply to the AI's reply from the customer address: the next poll ingests it into the same Conversation.
6. Send a new email with the same subject as step 3, not as a reply: it becomes a second Conversation.
