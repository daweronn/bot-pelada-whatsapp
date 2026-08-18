"""Sorteio de times a partir dos titulares da rodada fechada."""
from __future__ import annotations

import math

from .. import teams
from ..repositories import rodadas
from . import renderizacao
from .contexto import Contexto, Reply, apenas_admin


def quantidade_de_times(args: list[str], jogadores: int) -> int:
    for token in args:
        argumento = token.lower()
        if argumento.startswith("t") and argumento[1:].isdigit():
            por_time = max(1, int(argumento[1:]))
            return max(1, math.ceil(jogadores / por_time))
        if argumento.isdigit():
            return max(1, int(argumento))
    return max(1, math.ceil(jogadores / 5))


def sortear(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("sortear os times")

    rodada = rodadas.corrente(ctx.grupo.id)
    if rodada is None:
        return Reply("⚠️ Não existe lista pra sortear. Abra com *.abrirlista*.")
    if rodada.status == "aberta":
        return Reply(
            "⚠️ *Feche a lista antes de sortear.*\n"
            "Use *.fecharlista* quando todos tiverem confirmado."
        )

    titulares, _ = rodadas.separar(rodadas.presencas(rodada.id), rodada.vagas)
    if len(titulares) < 2:
        return Reply("⚠️ Preciso de pelo menos *2 jogadores* na lista pra sortear.")

    total = min(quantidade_de_times(ctx.args, len(titulares)), len(titulares))
    sorteados = teams.sortear([teams.Jogador(p.nome, p.overall) for p in titulares], total)

    linhas = ["🎲 *TIMES SORTEADOS* 🎲", renderizacao.LINHA]
    for posicao, time in enumerate(sorteados, 1):
        emoji = renderizacao.TIME_EMOJIS[(posicao - 1) % len(renderizacao.TIME_EMOJIS)]
        linhas.append(f"{emoji} *Time {posicao}*  ·  força {time.soma} · média {time.media:.1f}")
        linhas += [f"   • {j.name} _({j.overall})_" for j in time.jogadores]
        linhas.append("")
    linhas += [renderizacao.LINHA, "⚖️ _Times nivelados por faixas de overall e força acumulada._"]
    return Reply("\n".join(linhas))
