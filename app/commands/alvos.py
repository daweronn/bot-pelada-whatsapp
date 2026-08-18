"""Resolução do jogador alvo de um comando: menção, número ou nome."""
from __future__ import annotations

from dataclasses import dataclass

from ..messages import LID_SUFFIX, jid_to_phone
from ..models import Membro
from ..phones import canonical_phone, only_digits
from ..repositories import identidades, membros
from .contexto import Contexto, Reply


@dataclass(frozen=True)
class Alvo:
    identity_key: str
    phone_jid: str | None
    lid: str | None


def da_mencao(jid: str) -> Alvo:
    bruto = canonical_phone(jid_to_phone(jid))
    e_lid = jid.endswith(LID_SUFFIX)
    return Alvo(
        identity_key=identidades.resolver(bruto),
        phone_jid=None if e_lid else jid,
        lid=bruto if e_lid else None,
    )


def mencoes(ctx: Contexto) -> list[Alvo]:
    return [da_mencao(jid) for jid in ctx.msg.mentioned_jids]


def extrair_numero(tokens: list[str]) -> tuple[Alvo | None, list[str]]:
    for posicao, token in enumerate(tokens):
        digitos = only_digits(token)
        if len(digitos) >= 10:
            resto = tokens[:posicao] + tokens[posicao + 1 :]
            return Alvo(canonical_phone(token), f"{digitos}@s.whatsapp.net", None), resto
    return None, tokens


def extrair_overall(tokens: list[str]) -> tuple[int | None, list[str]]:
    for posicao, token in enumerate(tokens):
        if token.isdigit() and 0 <= int(token) <= 10:
            return int(token), tokens[:posicao] + tokens[posicao + 1 :]
    return None, tokens


def juntar_nome(tokens: list[str]) -> str:
    return " ".join(t for t in tokens if t != "-" and not t.startswith("@")).strip()


def identificar(ctx: Contexto, tokens: list[str]) -> tuple[Alvo | None, list[str]]:
    """Menção tem prioridade sobre número; nenhum dos dois consome o nome."""
    marcados = mencoes(ctx)
    if marcados:
        return marcados[0], [t for t in tokens if not t.startswith("@")]
    return extrair_numero(tokens)


def membro_existente(ctx: Contexto, tokens: list[str]) -> tuple[Membro | None, Reply | None]:
    """Resolve um membro já cadastrado por menção, número ou nome."""
    alvo, resto = identificar(ctx, tokens)
    if alvo:
        encontrado = membros.por_identidade(ctx.grupo.id, [alvo.identity_key])
        if not encontrado:
            return None, Reply("❓ Esse jogador não está cadastrado neste grupo.")
        return encontrado, None

    nome = juntar_nome(resto)
    if not nome:
        return None, Reply("❓ Informe o *número* ou o *nome* do jogador.")
    encontrados = membros.buscar_por_nome(ctx.grupo.id, nome)
    if not encontrados:
        return None, Reply(f"❓ Não achei ninguém chamado *{nome}*. Confira o nome ou use o número.")
    if len(encontrados) > 1:
        nomes = ", ".join(m.nome for m in encontrados[:6])
        return None, Reply(f"⚠️ Mais de um jogador parecido: {nomes}.\nUse o *número* pra não ter dúvida.")
    return encontrados[0], None
