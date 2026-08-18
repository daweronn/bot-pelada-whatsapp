"""Comandos da lista de presença de uma rodada."""
from __future__ import annotations

from ..config import settings
from ..models import e_nome_provisorio
from ..repositories import membros, rodadas
from . import alvos, renderizacao
from .contexto import Contexto, Reply, apenas_admin


def abrir(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("abrir a lista")
    vagas = next((int(t) for t in ctx.args if t.isdigit()), ctx.grupo.vagas_padrao)
    rodada, mensalistas = rodadas.abrir(ctx.grupo.id, vagas)
    nota = f"⭐ {mensalistas} mensalista(s) já entraram automaticamente.\n" if mensalistas else ""
    prefixo = (
        f"🟢 *LISTA ABERTA!* — {vagas} vagas\n"
        f"{nota}"
        "✅ Diaristas: mandem *.vou* pra confirmar.\n"
        "❌ Mensalista que não vai: mande *.naovou*.\n\n"
    )
    return Reply(renderizacao.lista(rodada, prefixo))


def fechar(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("fechar a lista")
    rodada = rodadas.aberta(ctx.grupo.id)
    if rodada is None:
        return Reply("ℹ️ Não tem lista aberta agora.")
    rodadas.fechar(rodada.id)
    return Reply("🔴 *LISTA FECHADA!*\n🎲 Monte os times com *.sorteiotimes*")


def mostrar(ctx: Contexto) -> Reply:
    return Reply(renderizacao.lista(rodadas.corrente(ctx.grupo.id)))


def confirmar(ctx: Contexto) -> Reply:
    rodada = rodadas.aberta(ctx.grupo.id)
    if rodada is None:
        return Reply("⚠️ Não tem lista aberta agora.\nPeça pro admin abrir com `.abrirlista`.")

    membro = ctx.membro()
    novo = membro is None
    apelido = ctx.msg.sender_name
    if novo:
        membro, _ = membros.salvar(
            ctx.grupo.id, ctx.identidade, apelido or "Diarista", settings.default_overall,
            mensalista=False, phone_jid=ctx.msg.sender_phone_jid, lid=ctx.msg.sender_lid or None,
        )
    elif apelido and e_nome_provisorio(membro.nome):
        membro, _ = membros.salvar(
            ctx.grupo.id, membro.identity_key, apelido, membro.overall,
            mensalista=membro.mensalista, phone_jid=ctx.msg.sender_phone_jid,
            lid=ctx.msg.sender_lid or None,
        )

    if not rodadas.confirmar(rodada.id, membro.id):
        return Reply("✅ Você *já está* na lista! 👍")
    extra = f"\n_(diarista, nota {settings.default_overall} — admin pode ajustar)_" if novo else ""
    return Reply(renderizacao.lista(rodada, f"✅ *Presença confirmada!*{extra}\n\n"))


def cancelar(ctx: Contexto) -> Reply:
    rodada = rodadas.aberta(ctx.grupo.id)
    if rodada is None:
        return Reply("⚠️ Não tem lista aberta agora.")
    membro = ctx.membro()
    if membro is None or not rodadas.cancelar(rodada.id, membro.id):
        return Reply("ℹ️ Você não estava na lista.")
    return Reply(
        renderizacao.lista(rodada, "👋 *Você saiu da lista.* O próximo da espera subiu. ⬆️\n\n")
    )


def incluir(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("usar o `.vai`")
    rodada = rodadas.aberta(ctx.grupo.id)
    if rodada is None:
        return Reply("⚠️ Abra a lista antes com *.abrirlista*.")

    alvo, resto = alvos.identificar(ctx, ctx.args)
    overall, resto = alvos.extrair_overall(resto)
    nome = alvos.juntar_nome(resto)

    if alvo is None:
        membro, erro = alvos.membro_existente(ctx, ctx.args)
        if erro:
            return erro
    else:
        atual = membros.por_identidade(ctx.grupo.id, [alvo.identity_key])
        membro, _ = membros.salvar(
            ctx.grupo.id,
            alvo.identity_key,
            nome or (atual.nome if atual else "Diarista"),
            overall if overall is not None else (atual.overall if atual else settings.default_overall),
            phone_jid=alvo.phone_jid,
            lid=alvo.lid,
        )

    rodadas.confirmar(rodada.id, membro.id)
    return Reply(
        renderizacao.lista(rodada, f"✅ *{membro.nome}* entrou na lista! _(overall {membro.overall})_\n\n")
    )


def excluir(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("tirar da lista")
    rodada = rodadas.aberta(ctx.grupo.id)
    if rodada is None:
        return Reply("⚠️ Não tem lista aberta agora.")
    membro, erro = alvos.membro_existente(ctx, ctx.args)
    if erro:
        return erro
    if not rodadas.cancelar(rodada.id, membro.id):
        return Reply("ℹ️ Esse jogador não estava na lista.")
    return Reply(
        renderizacao.lista(rodada, "🗑️ *Saiu da lista.* O próximo da espera subiu. ⬆️\n\n")
    )
