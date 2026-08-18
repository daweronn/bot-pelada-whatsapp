"""Comandos de mensalidade: marcar pagamento, isenção e ver quem deve."""
from __future__ import annotations

from decimal import Decimal

from ..models import jid_para_mencao
from ..repositories import pagamentos
from . import alvos
from .contexto import Contexto, Reply, apenas_admin


def _valor(valor: Decimal) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def mensalidade(ctx: Contexto) -> Reply:
    cfg = pagamentos.config(ctx.grupo.id)
    if cfg is None or not cfg.ativo:
        return Reply("ℹ️ Pagamento não configurado neste grupo.")
    linhas = ["💰 *Mensalidade*"]
    if cfg.valor is not None:
        linhas.append(f"Valor: {_valor(cfg.valor)}")
    if cfg.dia_vencimento:
        linhas.append(f"Vencimento: dia {cfg.dia_vencimento}")
    if cfg.pix_chave:
        linhas.append(f"PIX: {cfg.pix_chave}")
    return Reply("\n".join(linhas))


def pago(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("marcar pagamento")
    membro, erro = alvos.membro_existente(ctx, ctx.args)
    if erro:
        return erro
    pagamentos.marcar(ctx.grupo.id, membro.id, "pago")
    mencao = jid_para_mencao(membro.phone_jid, membro.lid)
    return Reply(f"✅ *{membro.nome}* marcado como *pago* este mês.", [mencao] if mencao else [])


def isento(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("marcar isenção")
    membro, erro = alvos.membro_existente(ctx, ctx.args)
    if erro:
        return erro
    pagamentos.marcar(ctx.grupo.id, membro.id, "isento")
    return Reply(f"🆓 *{membro.nome}* marcado como *isento* este mês.")


def naopago(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("desfazer pagamento")
    membro, erro = alvos.membro_existente(ctx, ctx.args)
    if erro:
        return erro
    pagamentos.remover(ctx.grupo.id, membro.id)
    return Reply(f"↩️ *{membro.nome}* voltou para *devendo* este mês.")


def devendo(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("ver quem está devendo")
    faltantes = pagamentos.devedores(ctx.grupo.id)
    if not faltantes:
        return Reply("🎉 Todos os mensalistas pagaram este mês!")
    linhas = [f"📌 *Devendo este mês* ({len(faltantes)}):"]
    mencoes: list[str] = []
    for membro in faltantes:
        linhas.append(f"• {membro.nome}")
        jid = jid_para_mencao(membro.phone_jid, membro.lid)
        if jid:
            mencoes.append(jid)
    return Reply("\n".join(linhas), mencoes)


def pagos(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("ver quem pagou")
    quitados = pagamentos.pagantes(ctx.grupo.id)
    if not quitados:
        return Reply("Ninguém pagou ainda este mês.")
    linhas = [f"✅ *Pagaram este mês* ({len(quitados)}):"]
    linhas += [f"• {membro.nome}" for membro in quitados]
    return Reply("\n".join(linhas))
