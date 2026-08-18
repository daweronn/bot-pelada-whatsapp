"""Grupo descartável e simulação de payloads da Evolution para os testes."""
from __future__ import annotations

from uuid import UUID, uuid4

from app import aprendizado, database
from app.commands import router
from app.commands.contexto import Reply
from app.database import buscar, executar, transacao
from app.messages import parse_event
from app.models import Grupo
from app.phones import canonical_phone

GRUPO_JID = f"{uuid4().int % 10**18}@g.us"
ADMIN_LID = "34810760273925@lid"
ADMIN_PHONE = "5522998720569@s.whatsapp.net"

_grupo: Grupo | None = None


def criar_grupo(vagas_padrao: int = 15) -> Grupo:
    global _grupo
    database.abrir()
    with transacao() as conn:
        _grupo = buscar(
            conn,
            Grupo,
            "INSERT INTO pelada.grupos (wa_group_jid, nome, vagas_padrao)"
            " VALUES (%s, %s, %s) RETURNING id, wa_group_jid, nome, vagas_padrao",
            (GRUPO_JID, "Pelada de Teste", vagas_padrao),
        )
        executar(
            conn,
            "INSERT INTO pelada.admins (grupo_id, identity_key, phone_jid, nome)"
            " VALUES (%s, %s, %s, %s)",
            (_grupo.id, canonical_phone("5522998720569"), ADMIN_PHONE, "Admin"),
        )
    return _grupo


def apagar_grupo() -> None:
    if _grupo is None:
        return
    with transacao() as conn:
        executar(conn, "DELETE FROM pelada.grupos WHERE id = %s", (_grupo.id,))
        executar(
            conn,
            "DELETE FROM pelada.identity_links WHERE lid = ANY(%s)",
            (_lids_usados(),),
        )
    database.fechar()


_lids: list[str] = []


def _lids_usados() -> list[str]:
    return _lids


def evento(
    texto: str,
    remetente: str = ADMIN_LID,
    telefone: str | None = None,
    apelido: str = "Tester",
    mencionados: list[str] | None = None,
) -> dict:
    mensagem: dict[str, object] = {"conversation": texto}
    if mencionados:
        mensagem = {
            "extendedTextMessage": {
                "text": texto,
                "contextInfo": {"mentionedJid": mencionados},
            }
        }
    chave: dict[str, object] = {
        "remoteJid": GRUPO_JID,
        "participant": remetente,
        "fromMe": False,
    }
    if telefone is None and remetente == ADMIN_LID:
        telefone = ADMIN_PHONE
    if telefone:
        chave["participantAlt"] = telefone
    if remetente.endswith("@lid"):
        digitos = remetente.split("@", 1)[0]
        if digitos not in _lids:
            _lids.append(digitos)
    return {
        "event": "messages.upsert",
        "data": {"key": chave, "pushName": apelido, "message": mensagem},
    }


def executar_comando(texto: str, **kwargs: object) -> Reply | None:
    msg = parse_event(evento(texto, **kwargs))
    assert msg is not None, f"não parseou: {texto}"
    aprendizado.aprender(_grupo, msg)
    return router.handle(_grupo, msg)


def grupo_id() -> UUID:
    return _grupo.id
