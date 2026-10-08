"""The Pub/Sub push webhook (push mode, §11.1), served through `GmailAdapter.router()`.

Gmail's notification is just `{emailAddress, historyId}` and never says which thread
changed (§12.1), so all the webhook does is wake that Mailbox's read. It answers 204 at
once; the read runs in the adapter's own loop. When `SUPPORT_GMAIL_PUBSUB_AUDIENCE` is
set, the request must carry a Google-signed token for that audience.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.support.adapter.gmail.settings import gmail_settings

logger = logging.getLogger(__name__)

# The Pub/Sub subscription's push endpoint: don't change it.
WEBHOOK_PATH = "/support/webhooks/gmail"


def _verify_pubsub_token(authorization: str | None) -> None:
    audience = gmail_settings.PUBSUB_AUDIENCE
    if not audience:
        # Verification not configured (e.g. local/dev) — accept unauthenticated.
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = authorization.removeprefix("Bearer ")
    try:
        id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


def build_webhook_router(on_push: Callable[[str], None]) -> APIRouter:
    """`on_push` is given the notified Mailbox's address, as Gmail sent it."""
    router = APIRouter(tags=["support"])

    @router.post(WEBHOOK_PATH, status_code=status.HTTP_204_NO_CONTENT)
    async def gmail_pubsub_push(request: Request) -> None:
        _verify_pubsub_token(request.headers.get("authorization"))

        body = await request.json()
        data_b64 = body.get("message", {}).get("data")
        email_address = None
        if data_b64:
            try:
                payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
                email_address = payload.get("emailAddress")
                logger.info(
                    "Gmail push notification for %s (historyId=%s)",
                    email_address,
                    payload.get("historyId"),
                )
            except (ValueError, UnicodeDecodeError):
                logger.warning("Gmail push notification with unparseable payload")

        if email_address:
            on_push(email_address)
        else:
            logger.warning(
                "Gmail push notification missing/unresolved emailAddress — "
                "relying on the backup poll"
            )

    return router
