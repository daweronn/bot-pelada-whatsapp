"""Servidor FastAPI que recebe o webhook da Evolution API."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response

from . import commands, db, evolution
from .config import settings
from .messages import parse_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pelada-bot")

app = FastAPI(title="Bot da Pelada")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    log.info("Banco inicializado em %s", settings.db_path)
    log.info("Admins: %s", ", ".join(settings.admin_numbers) or "(nenhum!)")


@app.get("/")
def health() -> dict:
    return {"status": "ok", "instance": settings.instance}


async def _process(body: dict) -> None:
    msg = parse_event(body)
    if msg is None:
        return
    # Não ignoramos fromMe: o próprio número da instância pode dar comandos.
    # As respostas do bot não começam com o prefixo, então não geram loop.

    # Se configurado, só atua no grupo permitido.
    if settings.allowed_group_jid and msg.chat_jid != settings.allowed_group_jid:
        return

    reply = commands.handle(msg)
    if reply is None:
        return

    log.info("[%s] %s -> resposta", msg.sender_phone, msg.text)
    try:
        await evolution.send_text(msg.chat_jid, reply.text, reply.mentions)
    except Exception as exc:  # não derruba o webhook se o envio falhar
        log.exception("Falha ao enviar resposta: %s", exc)


# A Evolution pode chamar /webhook ou /webhook/messages-upsert (modo por evento).
@app.post("/webhook")
@app.post("/webhook/{event_path}")
async def webhook(request: Request, event_path: str = "") -> Response:
    # Validação opcional por token (?token=...)
    if settings.webhook_token and request.query_params.get("token") != settings.webhook_token:
        return Response(status_code=401)

    try:
        body = await request.json()
    except Exception:
        return Response(status_code=204)

    await _process(body)
    return Response(status_code=200)
