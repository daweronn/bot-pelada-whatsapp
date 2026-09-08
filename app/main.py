"""Servidor FastAPI que recebe o webhook da Evolution API."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hmac import compare_digest

from fastapi import FastAPI, Request, Response

from . import aprendizado, database, evolution
from .commands import router
from .config import settings
from .messages import parse_event
from .repositories import grupos, mensagens

FILA_INTERVALO_S = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pelada-bot")


async def _processar_fila_uma_vez() -> None:
    for msg in mensagens.pendentes():
        jids = mensagens.destinos(msg)
        falhas = 0
        for jid in jids:
            try:
                await evolution.send_text(jid, msg.texto)
            except Exception as exc:
                falhas += 1
                log.warning("Fila: falha ao enviar %s para %s: %s", msg.id, jid, exc)
        mensagens.marcar_enviado(msg.id)
        log.info("Fila: msg %s -> %d grupo(s), %d falha(s)", msg.id, len(jids) - falhas, falhas)


async def _loop_fila() -> None:
    while True:
        try:
            await _processar_fila_uma_vez()
        except Exception as exc:
            log.exception("Fila: erro no loop: %s", exc)
        await asyncio.sleep(FILA_INTERVALO_S)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    database.abrir()
    log.info("Pool Postgres aberto | instância %s", settings.evolution_instance)
    tarefa_fila = asyncio.create_task(_loop_fila())
    yield
    tarefa_fila.cancel()
    database.fechar()


app = FastAPI(title="Bot da Pelada", lifespan=lifespan)


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok", "instance": settings.evolution_instance}


async def _process(body: dict) -> None:
    msg = parse_event(body)
    if msg is None or not msg.is_group:
        return

    grupo = grupos.por_jid(msg.chat_jid)
    if grupo is None:
        return

    aprendizado.aprender(grupo, msg)

    if settings.debug_payload and msg.text.startswith(router.PREFIX):
        log.info("PAYLOAD %s", json.dumps(body, ensure_ascii=False))

    reply = router.handle(grupo, msg)
    if reply is None:
        return

    log.info("[%s] %s | %s -> resposta", grupo.nome, msg.sender_phone, msg.text.split()[0])
    try:
        await evolution.send_text(msg.chat_jid, reply.text, reply.mentions)
    except Exception as exc:
        log.exception("Falha ao enviar resposta: %s", exc)


@app.post("/webhook")
@app.post("/webhook/{event_path}")
async def webhook(request: Request, event_path: str = "") -> Response:
    # O token é obrigatório: sem ele qualquer um forjaria o `participant` de um
    # admin e executaria comandos destrutivos (.remover, .noticia, .pago).
    if not compare_digest(request.query_params.get("token", ""), settings.webhook_token):
        return Response(status_code=401)

    try:
        body = await request.json()
    except Exception:
        return Response(status_code=204)

    await _process(body)
    return Response(status_code=200)
