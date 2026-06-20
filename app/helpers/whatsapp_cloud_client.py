from typing import Any

import httpx

from app.core.settings import Settings, get_settings


class WhatsAppCloudClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_text(
        self,
        *,
        to: str,
        text: str,
        phone_number_id: str | None = None,
    ) -> dict[str, Any]:
        # Envia a partir do número do tenant; cai no número de fallback das
        # settings quando não informado (setup single-tenant).
        sender_phone_number_id = phone_number_id or self._settings.whatsapp_phone_number_id
        url = (
            "https://graph.facebook.com/"
            f"{self._settings.meta_graph_api_version}/"
            f"{sender_phone_number_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def send_text_sync(
        self,
        *,
        to: str,
        text: str,
        phone_number_id: str | None = None,
    ) -> dict:
        """Envio síncrono para jobs/cron (idle sweep)."""

        sender_phone_number_id = phone_number_id or self._settings.whatsapp_phone_number_id
        url = (
            "https://graph.facebook.com/"
            f"{self._settings.meta_graph_api_version}/"
            f"{sender_phone_number_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self._settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

        with httpx.Client(timeout=10) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()


def get_whatsapp_client() -> WhatsAppCloudClient:
    return WhatsAppCloudClient(get_settings())
