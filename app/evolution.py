"""Cliente mínimo para enviar mensagens via Evolution API."""
from __future__ import annotations

import httpx

from .config import settings


async def send_text(to: str, text: str, mentions: list[str] | None = None) -> None:
    """Envia texto para um número/grupo (JID). `mentions` = lista de JIDs a marcar."""
    url = f"{settings.evolution_base_url}/message/sendText/{settings.evolution_instance}"
    payload: dict[str, object] = {"number": to, "text": text}
    if mentions:
        payload["mentioned"] = mentions
    headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
