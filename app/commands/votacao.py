"""Votações de MVP e Bagre sobre os titulares da rodada."""
from __future__ import annotations

from ..models import jid_para_mencao
from ..repositories import membros, rodadas, votacoes
from . import alvos, renderizacao
from .contexto import Contexto, Reply, apenas_admin

_ROTULOS = {"mvp": ("MVP", renderizacao.MVP), "bagre": ("Bagre", renderizacao.BAGRE)}


def _titulares(ctx: Contexto):
    rodada = rodadas.corrente(ctx.grupo.id)
    if rodada is None:
        return None, []
    titulares, _ = rodadas.separar(rodadas.presencas(rodada.id), rodada.vagas)
    return rodada, titulares


def abrir(ctx: Contexto, tipo: str) -> Reply:
    rotulo, emoji = _ROTULOS[tipo]
    if not ctx.admin:
        return apenas_admin(f"abrir a votação de {rotulo.upper()}")

    rodada, titulares = _titulares(ctx)
    if rodada is None:
        return Reply("⚠️ Não existe rodada pra votar.")
    if rodada.status == "aberta":
        return Reply("⚠️ *Feche a lista antes de abrir a votação.*")
    if len(titulares) < 2:
        return Reply("⚠️ É preciso ter pelo menos *2 titulares* para abrir a votação.")

    atual = votacoes.por_tipo(rodada.id, tipo)
    if atual and atual.aberta:
        return Reply(f"ℹ️ A votação de *{rotulo.upper()}* já está aberta.")

    votacoes.abrir(rodada.id, tipo)
    comando = "votemvp" if tipo == "mvp" else "votebagre"
    return Reply(
        f"{emoji} *VOTAÇÃO DE {rotulo.upper()} ABERTA!*\n"
        "Somente quem jogou pode votar em outro titular.\n"
        f"Vote com: *.{comando} @jogador*"
    )


def votar(ctx: Contexto, tipo: str) -> Reply:
    rotulo, _ = _ROTULOS[tipo]
    rodada, titulares = _titulares(ctx)
    votacao = votacoes.por_tipo(rodada.id, tipo) if rodada else None
    if votacao is None or not votacao.aberta:
        return Reply(f"⚠️ A votação de *{rotulo.upper()}* não está aberta.")

    marcados = alvos.mencoes(ctx)
    if len(marcados) != 1:
        comando = "votemvp" if tipo == "mvp" else "votebagre"
        return Reply(f"❓ Marque exatamente uma pessoa. Ex.: *.{comando} @jogador*")

    votante = ctx.membro()
    if votante is None or votante.id not in {p.membro_id for p in titulares}:
        return Reply("🚫 Só quem jogou como *titular* pode votar.")

    candidato = next(
        (p for p in titulares if p.identity_key == marcados[0].identity_key), None
    )
    if candidato is None:
        return Reply("🚫 O voto precisa ser em alguém que jogou como *titular*.")
    if candidato.membro_id == votante.id:
        return Reply("🚫 Não vale votar em si mesmo.")

    atualizado = votacoes.votar(votacao.id, votante.id, candidato.membro_id)
    mencao = jid_para_mencao(candidato.phone_jid, candidato.lid)
    acao = "atualizado" if atualizado else "computado"
    return Reply(
        f"✅ Voto de *{rotulo}* {acao} para *{candidato.nome}*.",
        [mencao] if mencao else [],
    )


def fechar(ctx: Contexto, tipo: str) -> Reply:
    rotulo, emoji = _ROTULOS[tipo]
    if not ctx.admin:
        return apenas_admin(f"fechar a votação de {rotulo.upper()}")

    rodada, _ = _titulares(ctx)
    votacao = votacoes.por_tipo(rodada.id, tipo) if rodada else None
    if votacao is None or not votacao.aberta:
        return Reply(f"ℹ️ A votação de *{rotulo.upper()}* não está aberta.")

    placar = votacoes.fechar(votacao.id)
    if not placar:
        return Reply(f"📭 *VOTAÇÃO DE {rotulo.upper()} ENCERRADA*\nNenhum voto foi registrado.")

    maior = placar[0].votos
    empatados = [resultado for resultado in placar if resultado.votos == maior]
    if len(empatados) > 1:
        nomes = ", ".join(r.nome for r in empatados)
        mencoes = [
            jid for jid in (jid_para_mencao(r.phone_jid, r.lid) for r in empatados) if jid
        ]
        return Reply(
            f"🤝 *EMPATE NA VOTAÇÃO DE {rotulo.upper()}!*\n"
            f"{nomes} receberam *{maior} voto(s)* cada.\n"
            "Ninguém ganhou nem perdeu ponto.",
            mencoes,
        )

    vencedor = placar[0]
    delta = 1 if tipo == "mvp" else -1
    atualizado = membros.ajustar_overall(vencedor.membro_id, delta)
    if vencedor.overall == atualizado.overall:
        mudanca = f"já estava no limite de *{atualizado.overall}/10*"
    else:
        mudanca = f"overall *{'+1' if delta > 0 else '-1'}* → agora *{atualizado.overall}/10*"

    mencao = jid_para_mencao(vencedor.phone_jid, vencedor.lid)
    frase = "Craque da rodada" if tipo == "mvp" else "Hoje a bola cobrou"
    return Reply(
        f"{emoji} *{rotulo.upper()} DA PELADA: {vencedor.nome}!*\n"
        f"{frase}, com *{vencedor.votos} voto(s)*.\n"
        f"📊 {mudanca}.",
        [mencao] if mencao else [],
    )
