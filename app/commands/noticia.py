"""Broadcast de notícia a partir do grupo principal, restrito à arena dele."""
from __future__ import annotations

from ..repositories import mensagens
from .contexto import Contexto, Reply, apenas_admin


def noticia(ctx: Contexto) -> Reply:
    if not ctx.grupo.principal:
        return Reply("🚫 O `.noticia` só funciona no *grupo principal*.")
    if not ctx.admin:
        return apenas_admin("enviar notícias")
    if ctx.grupo.arena_id is None:
        return Reply("🚫 Este grupo não está vinculado a uma arena.")
    texto = " ".join(ctx.args).strip()
    if not texto:
        return Reply("Uso: `.noticia <mensagem>` — envia para *todos os grupos da arena*.")
    mensagens.enfileirar("arena", texto, arena_id=ctx.grupo.arena_id)
    return Reply("📢 Notícia enfileirada para *todos os grupos da arena*.")
