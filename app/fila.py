"""Laço de envio da fila: um envio por vez, espaçado, com recuo nas falhas."""
from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from uuid import UUID

from . import evolution
from .config import settings
from .models import Envio
from .repositories import envios, mensagens

log = logging.getLogger("pelada-bot")

Enviar = Callable[[str, str], Awaitable[None]]


async def _tentar(envio: Envio, enviar: Enviar) -> None:
    try:
        await enviar(envio.wa_group_jid, envio.texto)
    except Exception as exc:
        erro = f"{type(exc).__name__}: {exc}"
        if envio.tentativas >= settings.fila_max_tentativas:
            envios.marcar_erro(envio.id, erro)
            log.warning("Fila: envio %s desistido após %d tentativas: %s", envio.id, envio.tentativas, erro)
        else:
            # tentativas < fila_max_tentativas, então o expoente tem teto e não estoura.
            espera = settings.fila_espera_base_s * 4 ** (envio.tentativas - 1)
            envios.reagendar(envio.id, erro, espera)
            log.warning("Fila: envio %s falhou (tentativa %d), nova em %ds: %s", envio.id, envio.tentativas, espera, erro)
        return
    envios.marcar_enviado(envio.id)
    log.info("Fila: msg %s enviada para %s", envio.mensagem_id, envio.wa_group_jid)


async def processar_uma_vez(enviar: Enviar = evolution.send_text, mensagem_id: UUID | None = None) -> bool:
    """Distribui, tenta um envio (só da mensagem dada, se houver) e conclui; True se houve tentativa."""
    mensagens.distribuir()
    envio = envios.reservar_proximo(settings.fila_lease_s, mensagem_id)
    if envio is not None:
        await _tentar(envio, enviar)
    mensagens.concluir()
    return envio is not None


async def rodar() -> None:
    """Laço eterno; espaça os disparos ao acaso para o WhatsApp não ver rajada."""
    while True:
        try:
            tentou = await processar_uma_vez()
        except Exception as exc:
            log.exception("Fila: erro no laço: %s", exc)
            tentou = False
        if tentou:
            await asyncio.sleep(random.uniform(settings.fila_intervalo_min_s, settings.fila_intervalo_max_s))
        else:
            await asyncio.sleep(settings.fila_ociosa_s)
