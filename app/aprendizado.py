"""Captura de identidade a partir de qualquer mensagem recebida.

O telefone discável só aparece quando a pessoa fala no grupo. Toda mensagem
é uma oportunidade de aprender o par LID/telefone e completar o phone_jid.
"""
from __future__ import annotations

from .messages import IncomingMessage
from .models import Grupo
from .repositories import identidades, membros


def aprender(grupo: Grupo, msg: IncomingMessage) -> None:
    telefone = msg.phone_candidates[0] if msg.phone_candidates else ""
    if msg.sender_lid and telefone:
        identidades.vincular(msg.sender_lid, telefone)

    chave = telefone or msg.sender_lid
    if chave and (msg.sender_phone_jid or msg.sender_lid):
        membros.registrar_contato(
            grupo.id, chave, msg.sender_phone_jid, msg.sender_lid or None
        )
