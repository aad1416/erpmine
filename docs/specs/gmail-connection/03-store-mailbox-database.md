# Store Mailbox Database

**Status:** Draft  
**Purpose:** Make Gmail support mailboxes durable, store-owned records in the database.

This is a living, blueprint-level spec. Implementation details will be added as decisions are made.

## Outcome

The platform has one reliable place to know which Gmail mailboxes belong to each store and whether each mailbox should currently operate.

## Scope

1. Represent a Gmail mailbox connection owned by a store.
2. Preserve the authorization needed to operate the mailbox securely.
3. Track whether the mailbox is connected, enabled, disabled, or needs attention.
4. Support reconnection and disconnection.
5. Preserve the mailbox's processing position and operational health.

## Established decisions

- A mailbox connection is more than an email address.
- Disabling keeps the connection but stops processing.
- Disconnecting removes Gmail access and stops processing.
- Existing support history remains after disabling or disconnecting.

## Completion

- Store mailbox connections persist independently of application configuration.
- Their lifecycle can be managed without losing existing support history.
- Other parts of the platform can discover which mailboxes are ready to operate.

## Open decisions

- Mailbox ownership rules
- Allowed number of mailboxes per store
- Final lifecycle and health model
- Retention expectations after disconnection

## Related specs

- [Google Production Readiness](01-google-production-readiness.md)
- [Gmail Connection Flow](02-gmail-connection-flow.md)
- [Gmail Adapter Database Integration](04-gmail-adapter-database-integration.md)
