"""Formatação das mensagens enviadas ao grupo."""
from __future__ import annotations

from ..models import Membro, Presenca, Rodada
from ..repositories import rodadas

LINHA = "━━━━━━━━━━━━━━━"
TIME_EMOJIS = ("🟦", "🟥", "🟩", "🟨", "🟪", "🟧", "⬛", "⬜")
MENSALISTA = "⭐"
DIARISTA = "🔹"
SEM_NUMERO = "📵"
MVP = "🏆"
BAGRE = "🐟"

_LEGENDA = f"_{MENSALISTA} mensalista   {DIARISTA} diarista   {SEM_NUMERO} sem número_"


def _marcador(mensalista: bool, phone_jid: str | None) -> str:
    tipo = MENSALISTA if mensalista else DIARISTA
    return f"{tipo}{SEM_NUMERO}" if not phone_jid else tipo


def lista(rodada: Rodada | None, prefixo: str = "") -> str:
    if rodada is None:
        return f"{prefixo}📝 Nenhuma lista aberta ainda."

    confirmados = rodadas.presencas(rodada.id)
    cabecalho = "🟢 ABERTA" if rodada.status == "aberta" else "🔴 FECHADA"
    if not confirmados:
        return (
            f"{prefixo}📝 *LISTA DA PELADA* ({cabecalho})\n{LINHA}\n"
            f"Ninguém confirmado ainda. ({rodada.vagas} vagas)"
        )

    titulares, espera = rodadas.separar(confirmados, rodada.vagas)
    linhas = [
        f"{prefixo}📝 *LISTA DA PELADA* ({cabecalho})",
        f"👥 Titulares: {len(titulares)}/{rodada.vagas}",
        LINHA,
    ]
    linhas += _numerar(titulares)
    if espera:
        linhas += [LINHA, f"⏳ *Lista de espera* ({len(espera)}):"]
        linhas += _numerar(espera)
    linhas += [LINHA, _LEGENDA]
    return "\n".join(linhas)


def _numerar(presencas: list[Presenca]) -> list[str]:
    return [
        f"{posicao}. {_marcador(p.mensalista, p.phone_jid)} {p.nome}"
        for posicao, p in enumerate(presencas, 1)
    ]


def elenco(membros: list[Membro]) -> str:
    if not membros:
        return "📋 Nenhum jogador cadastrado ainda.\nUse `.cadastro` pra começar."
    linhas = [f"📋 *JOGADORES CADASTRADOS* ({len(membros)})", LINHA]
    linhas += [
        f"{_marcador(m.mensalista, m.phone_jid)} {m.nome} — *{m.overall}*" for m in membros
    ]
    linhas += [LINHA, _LEGENDA]
    return "\n".join(linhas)
