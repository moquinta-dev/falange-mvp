import hashlib
import hmac
from typing import Any


def extract_whatsapp_message(payload: dict[str, Any]) -> dict[str, str] | None:
    try:
        value = payload["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if not messages:
            return None

        # phone_number_id identifica o número (e portanto o tenant) que recebeu
        # a mensagem. Vem do metadata do evento da Meta.
        phone_number_id = value.get("metadata", {}).get("phone_number_id", "")

        message = messages[0]
        message_id = message.get("id", "")

        if message.get("type") != "text":
            return {
                "from": message["from"],
                "text": "MESSAGE_TYPE_NOT_SUPPORTED",
                "message_id": message_id,
                "phone_number_id": phone_number_id,
            }

        return {
            "from": message["from"],
            "text": message["text"]["body"],
            "message_id": message_id,
            "phone_number_id": phone_number_id,
        }
    except (KeyError, IndexError, TypeError):
        return None


def verify_meta_signature(
    body: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        app_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
