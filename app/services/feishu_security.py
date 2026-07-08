import hashlib
import hmac


def verify_event_token(payload: dict, expected_token: str) -> bool:
    if not expected_token:
        return True
    return payload.get("token") == expected_token


def verify_webhook_signature(timestamp: str, nonce: str, body: bytes, encrypt_key: str, signature: str) -> bool:
    """Verify Feishu v2 event signature.

    Algorithm: sha256(timestamp + nonce + encrypt_key + body)
    """
    if not encrypt_key:
        return True
    if not timestamp or not nonce or not signature:
        return False
    content = f"{timestamp}{nonce}{encrypt_key}".encode("utf-8") + body
    digest = hashlib.sha256(content).hexdigest()
    return hmac.compare_digest(digest, signature)

