"""Extração de campos úteis do payload de webhook da Evolution API."""
from __future__ import annotations

from dataclasses import dataclass, field

from .phones import canonical_phone

PHONE_SUFFIX = "@s.whatsapp.net"


def jid_to_phone(jid: str) -> str:
    """'5511999999999:12@s.whatsapp.net' -> '5511999999999'."""
    if not jid:
        return ""
    local = jid.split("@", 1)[0]
    local = local.split(":", 1)[0]  # remove sufixo de device
    return "".join(ch for ch in local if ch.isdigit())


def phone_to_jid(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"{digits}@s.whatsapp.net"


def _collect_phone_candidates(data: dict, key: dict) -> list[str]:
    """Procura o telefone REAL (@s.whatsapp.net) em todos os campos onde a
    Evolution costuma colocá-lo — porque o `participant` pode vir como LID.
    Devolve uma lista de números já em forma canônica."""
    raw: list[str] = []
    for k in ("participant", "participantPn", "participantAlt", "senderPn", "remoteJid"):
        v = key.get(k)
        if isinstance(v, str):
            raw.append(v)
    for k in ("participant", "participantPn", "participantAlt", "sender", "senderPn"):
        v = data.get(k)
        if isinstance(v, str):
            raw.append(v)

    cands: list[str] = []
    for jid in raw:
        if jid.endswith(PHONE_SUFFIX):  # só telefone de verdade, ignora @lid/@g.us
            c = canonical_phone(jid_to_phone(jid))
            if c and c not in cands:
                cands.append(c)
    return cands


@dataclass
class IncomingMessage:
    chat_jid: str          # de onde veio (grupo @g.us ou contato @s.whatsapp.net)
    sender_jid: str        # quem enviou (pode ser LID)
    sender_phone: str      # melhor identidade canônica disponível
    sender_name: str
    text: str
    from_me: bool
    is_group: bool
    phone_candidates: list[str] = field(default_factory=list)  # todos os telefones reais achados
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
    is_group = chat_jid.endswith("@g.us")
    from_me = bool(key.get("fromMe", False))

    # Em grupo o remetente vem em participant; em DM é o próprio remoteJid.
    sender_jid = key.get("participant") or chat_jid

    # Identidade: preferimos um telefone REAL; se só houver LID, caímos nele.
    phone_candidates = _collect_phone_candidates(data, key)
    if phone_candidates:
        sender_phone = phone_candidates[0]
    else:
        sender_phone = canonical_phone(jid_to_phone(sender_jid))

    sender_name = data.get("pushName", "") or ""

    message = data.get("message", {}) or {}
    text = ""
    mentioned: list[str] = []

    if "conversation" in message:
        text = message.get("conversation", "") or ""
    ext = message.get("extendedTextMessage")
    if ext:
        text = ext.get("text", "") or text
        ctx = ext.get("contextInfo", {}) or {}
        mentioned = ctx.get("mentionedJid", []) or []

    text = text.strip()
    if not text:
        return None

    return IncomingMessage(
        chat_jid=chat_jid,
        sender_jid=sender_jid,
        sender_phone=sender_phone,
        sender_name=sender_name,
        text=text,
        from_me=from_me,
        is_group=is_group,
        phone_candidates=phone_candidates,
        mentioned_jids=mentioned,
    )
