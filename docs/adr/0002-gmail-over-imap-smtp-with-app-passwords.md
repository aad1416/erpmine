# Connect Gmail over IMAP/SMTP with app passwords, beside the Gmail API adapter

The Gmail API adapter needs the `gmail.modify` scope, which Google classes as restricted: using it with real store mailboxes requires our OAuth app to pass Google's verification and a paid security assessment. To let stores connect Gmail without waiting on that, we add a second Connection Method: IMAP to read and SMTP to reply, authenticated with a Google app password. It runs beside the Gmail API adapter rather than replacing it, and each Mailbox uses exactly one Connection Method.

## Considered Options

- **Wait for Google verification and use only the Gmail API.** Rejected for now: it blocks every store connection on an external review we don't control.
- **Replace the Gmail API adapter with IMAP.** Rejected: the Gmail API gives push notifications and history-based sync, and stays the long-term path once verified.

## Consequences

- App passwords require 2-Step Verification, Google calls them "not recommended", and Workspace admins can block them. Some stores won't be able to connect this way.
- A Google password change revokes the app password, so the Mailbox stops until it gets a new one.
- Gmail's IMAP extensions give the same message and thread IDs as the Gmail API, so a Mailbox can move between Connection Methods later. Moving it is not supported today, and its open conversations would not carry over automatically.
