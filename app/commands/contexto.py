"""Contexto resolvido de um comando: quem falou, em qual grupo, com que poder."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..messages import IncomingMessage, jid_to_phone
from ..models import Grupo, Membro
from ..phones import canonical_phone
from ..repositories import grupos, identidades, membros


@dataclass
class Reply:
    text: str
    mentions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Contexto:
    grupo: Grupo
    msg: IncomingMessage
    identidades: list[str]
    admin: bool
    args: list[str]

    @property
    def identidade(self) -> str:
        return self.identidades[0] if self.identidades else ""

    def membro(self) -> Membro | None:
        return membros.por_identidade(self.grupo.id, self.identidades)


def identidades_do_remetente(msg: IncomingMessage) -> list[str]:
    brutas = list(msg.phone_candidates)
    lid = canonical_phone(jid_to_phone(msg.sender_jid))
    if lid and lid not in brutas:
        brutas.append(lid)
    if not brutas:
        brutas = [canonical_phone(msg.sender_phone)]
    return identidades.resolver_varias([b for b in brutas if b])


def montar(grupo: Grupo, msg: IncomingMessage, args: list[str]) -> Contexto:
    chaves = identidades_do_remetente(msg)
    return Contexto(
        grupo=grupo,
        msg=msg,
        identidades=chaves,
        admin=grupos.e_admin(grupo.id, chaves),
        args=args,
    )


def apenas_admin(acao: str) -> Reply:
    return Reply(f"🚫 *Apenas o admin* pode {acao}.")
