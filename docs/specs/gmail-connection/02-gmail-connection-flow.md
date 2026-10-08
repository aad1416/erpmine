# Gmail Connection Flow

**Status:** Draft  
**Purpose:** Let a store administrator connect and manage a Gmail support mailbox from the product.

This is a living, blueprint-level spec. Implementation details will be added as decisions are made.

## Outcome

A store administrator can connect Gmail through Google and then see and manage the resulting mailbox connection inside the product.

## Scope

1. Start a Gmail connection from the frontend.
2. Complete authorization through Google.
3. Return to the correct store and register the approved mailbox.
4. Show the connected mailbox and its current status.
5. Provide enable, disable, reconnect, and disconnect actions.
6. Present clear success, rejection, and recovery journeys.

## Established decisions

- The flow supports independently owned Gmail accounts through OAuth.
- Google handles Google account authentication and consent.
- Sensitive Google credentials remain in the backend.
- Each connection belongs to a store.

## Completion

- A store administrator can complete the full connection journey.
- The connected mailbox appears in store settings.
- The mailbox can be managed throughout its lifecycle.

## Open decisions

- Final user experience and wording
- Store administrator permissions
- Connection and recovery states presented to users

## Related specs

- [Google Production Readiness](01-google-production-readiness.md)
- [Store Mailbox Database](03-store-mailbox-database.md)
- [Gmail Adapter Database Integration](04-gmail-adapter-database-integration.md)
