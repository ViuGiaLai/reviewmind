from __future__ import annotations

import base64
import hashlib
import hmac
import time


class WebhookVerificationError(ValueError):
    pass


def verify_svix_webhook(
    body: bytes,
    *,
    message_id: str,
    timestamp: str,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> None:
    """Verify Clerk/Svix webhook authenticity and replay window."""
    if not all((message_id, timestamp, signature_header, secret)):
        raise WebhookVerificationError("Missing webhook verification data.")
    try:
        timestamp_value = int(timestamp)
    except ValueError as error:
        raise WebhookVerificationError("Invalid webhook timestamp.") from error
    if abs(int(time.time()) - timestamp_value) > tolerance_seconds:
        raise WebhookVerificationError("Webhook timestamp is outside the replay window.")

    encoded_secret = secret.removeprefix("whsec_")
    try:
        key = base64.b64decode(encoded_secret, validate=True)
    except ValueError as error:
        raise WebhookVerificationError("Invalid webhook secret.") from error
    signed = f"{message_id}.{timestamp}.".encode("utf-8") + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    supplied = [
        item.split(",", 1)[1]
        for item in signature_header.split()
        if item.startswith("v1,") and "," in item
    ]
    if not supplied or not any(hmac.compare_digest(expected, item) for item in supplied):
        raise WebhookVerificationError("Invalid webhook signature.")
