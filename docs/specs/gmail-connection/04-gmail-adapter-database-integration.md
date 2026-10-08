# Gmail Adapter Database Integration

**Status:** Draft  
**Purpose:** Operate store Gmail mailboxes from database connections instead of hardcoded settings.

This is a living, blueprint-level spec. Implementation details will be added as decisions are made.

## Outcome

The existing Gmail adapter automatically operates every enabled store mailbox registered in the database.

## Scope

1. Discover active store mailbox connections from the database.
2. Start processing newly enabled mailboxes.
3. Stop processing disabled or disconnected mailboxes.
4. Keep each mailbox's processing isolated from other mailboxes.
5. Move the current manually configured Gmail connection into the new model.

## Established decisions

- The existing Gmail adapter remains the mailbox-processing engine.
- The database becomes the source of truth for store Gmail connections.
- A problem with one mailbox must not stop other mailboxes.
- Hardcoded mailbox configuration is removed after migration.

## Completion

- The adapter no longer depends on a hardcoded Gmail mailbox.
- Enabled database mailboxes are processed automatically.
- Disable, reconnect, and disconnect changes are respected.
- The currently connected mailbox continues operating after migration.

## Open decisions

- Mailbox discovery and activation approach
- Migration sequence for the existing mailbox
- Operational visibility for mailbox processing

## Related specs

- [Google Production Readiness](01-google-production-readiness.md)
- [Gmail Connection Flow](02-gmail-connection-flow.md)
- [Store Mailbox Database](03-store-mailbox-database.md)
