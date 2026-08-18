"""Extração de campos úteis do payload de webhook da Evolution API."""
from __future__ import annotations

from dataclasses import dataclass, field

from .phones import canonical_phone

PHONE_SUFFIX = "@s.whatsapp.net"
LID_SUFFIX = "@lid"

_CAMPOS_KEY = ("participant", "participantPn", "participantAlt", "senderPn", "remoteJid")
_CAMPOS_DATA = ("participant", "participantPn", "participantAlt", "sender", "senderPn")


def jid_to_phone(jid: str) -> str:
    """'5511999999999:12@s.whatsapp.net' -> '5511999999999'."""
    if not jid:
        return ""
    local = jid.split("@", 1)[0]
    local = local.split(":", 1)[0]
    return "".join(ch for ch in local if ch.isdigit())


def phone_to_jid(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"{digits}{PHONE_SUFFIX}"


def _coletar_phone_jids(data: dict, key: dict) -> list[str]:
    """Telefones REAIS (@s.whatsapp.net) presentes no payload, como chegaram.

    O `participant` pode vir como LID; o número discável costuma estar no
    `participantAlt`. Preservamos o JID original — a chave canônica descarta o
    9º dígito e não serve para enviar mensagem."""
    brutos: list[str] = []
    for campo in _CAMPOS_KEY:
        valor = key.get(campo)
        if isinstance(valor, str):
            brutos.append(valor)
    for campo in _CAMPOS_DATA:
        valor = data.get(campo)
        if isinstance(valor, str):
            brutos.append(valor)

    jids: list[str] = []
    for jid in brutos:
        if jid.endswith(PHONE_SUFFIX) and jid not in jids:
            jids.append(jid)
    return jids


@dataclass
class IncomingMessage:
    chat_jid: str
    sender_jid: str
    sender_phone: str
    sender_lid: str
    sender_phone_jid: str | None
    sender_name: str
    text: str
    from_me: bool
    is_group: bool
    phone_candidates: list[str] = field(default_factory=list)
    mentioned_jids: list[str] = field(default_factory=list)


def parse_event(body: dict) -> IncomingMessage | None:
    """Converte o corpo do webhook em IncomingMessage, ou None se não for mensagem útil."""
    event = body.get("event", "")
    if event and event.replace(".", "_") != "messages_upsert":
        return None

    data = body.get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        return None

    key = data.get("key", {}) or {}
    chat_jid = key.get("remoteJid", "") or ""
    sender_jid = key.get("participant") or chat_jid

    phone_jids = _coletar_phone_jids(data, key)
    candidatos: list[str] = []
    for jid in phone_jids:
        canonico = canonical_phone(jid_to_phone(jid))
        if canonico and canonico not in candidatos:
            candidatos.append(canonico)

    sender_phone = candidatos[0] if candidatos else canonical_phone(jid_to_phone(sender_jid))
    sender_lid = (
        canonical_phone(jid_to_phone(sender_jid)) if sender_jid.endswith(LID_SUFFIX) else ""
    )

    message = data.get("message", {}) or {}
    text = message.get("conversation", "") or ""
    mencionados: list[str] = []
    estendida = message.get("extendedTextMessage")
    if estendida:
        text = estendida.get("text", "") or text
        contexto = estendida.get("contextInfo", {}) or {}
        mencionados = contexto.get("mentionedJid", []) or []

    text = text.strip()
    if not text:
        return None

    return IncomingMessage(
        chat_jid=chat_jid,
        sender_jid=sender_jid,
        sender_phone=sender_phone,
        sender_lid=sender_lid,
        sender_phone_jid=phone_jids[0] if phone_jids else None,
        sender_name=(data.get("pushName", "") or "").strip(),
        text=text,
        from_me=bool(key.get("fromMe", False)),
        is_group=chat_jid.endswith("@g.us"),
        phone_candidates=candidatos,
        mentioned_jids=mencionados,
    )
