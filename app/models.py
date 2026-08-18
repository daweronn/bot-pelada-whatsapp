"""Entidades do domínio, espelhando as colunas retornadas pelas consultas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class Grupo:
    id: UUID
    wa_group_jid: str
    nome: str
    vagas_padrao: int
    principal: bool = False


@dataclass(frozen=True)
class MensagemFila:
    id: UUID
    escopo: str
    grupo_id: UUID | None
    arena_id: UUID | None
    texto: str


@dataclass(frozen=True)
class Membro:
    id: UUID
    grupo_id: UUID
    identity_key: str
    phone_jid: str | None
    lid: str | None
    nome: str
    overall: int
    mensalista: bool


@dataclass(frozen=True)
class Rodada:
    id: UUID
    grupo_id: UUID
    data: date
    vagas: int
    status: str


@dataclass(frozen=True)
class Presenca:
    membro_id: UUID
    identity_key: str
    phone_jid: str | None
    lid: str | None
    nome: str
    overall: int
    mensalista: bool
    ordem: int


@dataclass(frozen=True)
class Votacao:
    id: UUID
    rodada_id: UUID
    tipo: str
    aberta: bool


@dataclass(frozen=True)
class ResultadoVoto:
    membro_id: UUID
    nome: str
    phone_jid: str | None
    lid: str | None
    overall: int
    votos: int


@dataclass(frozen=True)
class Identidade:
    identity_key: str
    lid: str | None
    phone_jid: str | None


PREFIXO_PROVISORIO = "Jogador "


def nome_provisorio(identity_key: str) -> str:
    return f"{PREFIXO_PROVISORIO}{identity_key[-5:]}"


def e_nome_provisorio(nome: str) -> bool:
    return nome.startswith(PREFIXO_PROVISORIO)


def jid_para_mencao(phone_jid: str | None, lid: str | None) -> str | None:
    if phone_jid:
        return phone_jid
    return f"{lid}@lid" if lid else None
