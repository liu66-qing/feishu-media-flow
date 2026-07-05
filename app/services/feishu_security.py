import base64
import hashlib
import hmac


def verify_event_token(payload: dict, expected_token: str) -> bool:
    if not expected_token:
        return True
    return payload.get("token") == expected_token


def verify_webhook_signature(timestamp: str, nonce: str, body: bytes, secret: str, signature: str) -> bool:
    if not secret:
        return True
    if not timestamp or not nonce or not signature:
        return False
    msg = f"{timestamp}{nonce}{secret}".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)

