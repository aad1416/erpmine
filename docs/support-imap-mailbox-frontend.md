# Store IMAP mailbox settings: frontend guide

These endpoints manage the IMAP mailbox for the store in the signed-in admin's token. They are available when support is enabled. Send the admin token with both requests; the server takes `storeId` from that token. There is one IMAP mailbox per store.

## Read the mailbox

`GET /support/mailboxes/imap`

Returns `200` with the saved settings, or `404` when this store has no IMAP mailbox yet. The password is never returned.

## Create or update the mailbox

`PUT /support/mailboxes/imap` with a JSON body. The first request needs `mailbox` and `app_password`; all other fields are optional and use the defaults below. It returns `201` when it creates a row and `200` when it updates one. On later requests, send only fields that changed. Omitted fields retain their saved values, including the password. Explicit `null` is rejected.

| Field | First-save default | Notes |
| --- | --- | --- |
| `mailbox` | Required | Email address; trimmed and converted to lowercase. |
| `app_password` | Required | Nonblank IMAP/SMTP app password; write only. |
| `imap_host` | `imap.gmail.com` | Nonblank hostname. |
| `imap_port` | `993` | Integer from 1 to 65535. |
| `imap_tls_mode` | `ssl` | `ssl` or `starttls`. |
| `smtp_host` | `smtp.gmail.com` | Nonblank hostname. |
| `smtp_port` | `465` | Integer from 1 to 65535. |
| `smtp_tls_mode` | `ssl` | `ssl` or `starttls`. |

Example first save:

```http
PUT /support/mailboxes/imap
Authorization: Bearer <admin token>
Content-Type: application/json

{"mailbox":"support@example.com","app_password":"<app password>"}
```

Example partial update:

```json
{"smtp_host":"smtp.example.com","smtp_port":587,"smtp_tls_mode":"starttls"}
```

The response to GET and PUT has this shape:

```json
{
  "mailbox": "support@example.com",
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_tls_mode": "ssl",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 465,
  "smtp_tls_mode": "ssl",
  "restart_required": true
}
```

`restart_required` reflects the current startup-snapshot behavior: saved changes take effect after the app restarts. It does not indicate whether a restart has already happened. Changing the mailbox address resets its polling cursor; other edits preserve the cursor.

## Errors and UI behavior

| Status | Meaning |
| --- | --- |
| `401` or `403` | Missing/invalid admin access, or admin token has no usable `storeId`. |
| `404` | No mailbox exists for this store (GET only). Show the create form. |
| `409` | Mailbox address is already configured for another store or adapter. |
| `422` | Invalid field, explicit `null`, or first save missing `mailbox` or `app_password`. |

Load GET when the settings page opens. If it returns `404`, show a new mailbox form with the defaults above. On edits, leave the password blank in the UI and omit `app_password` from PUT unless the admin entered a replacement. After a successful PUT, show that an app restart is required. The frontend separately sets the store support email in Lyndom; this API only saves the IMAP connection.
