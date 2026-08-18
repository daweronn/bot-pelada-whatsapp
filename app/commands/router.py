"""Despacho dos comandos recebidos no grupo."""
from __future__ import annotations

from collections.abc import Callable

from ..models import Grupo
from ..messages import IncomingMessage
from . import ajuda, cadastro, lista, noticia, pagamento, sorteio, votacao
from .contexto import Contexto, Reply, montar

PREFIX = "."

_HANDLERS: dict[str, Callable[[Contexto], Reply]] = {
    "cadastro": cadastro.cadastrar,
    "remover": cadastro.remover,
    "mensalista": lambda ctx: cadastro.definir_tipo(ctx, True),
    "diarista": lambda ctx: cadastro.definir_tipo(ctx, False),
    "jogadores": cadastro.listar,
    "abrirlista": lista.abrir,
    "fecharlista": lista.fechar,
    "lista": lista.mostrar,
    "vou": lista.confirmar,
    "naovou": lista.cancelar,
    "vai": lista.incluir,
    "naovai": lista.excluir,
    "sorteiotimes": sorteio.sortear,
    "sortear": sorteio.sortear,
    "abrirmvp": lambda ctx: votacao.abrir(ctx, "mvp"),
    "votemvp": lambda ctx: votacao.votar(ctx, "mvp"),
    "fecharmvp": lambda ctx: votacao.fechar(ctx, "mvp"),
    "abrirbagre": lambda ctx: votacao.abrir(ctx, "bagre"),
    "votebagre": lambda ctx: votacao.votar(ctx, "bagre"),
    "fecharbagre": lambda ctx: votacao.fechar(ctx, "bagre"),
    "noticia": noticia.noticia,
    "mensalidade": pagamento.mensalidade,
    "pago": pagamento.pago,
    "isento": pagamento.isento,
    "naopago": pagamento.naopago,
    "devendo": pagamento.devendo,
    "pagos": pagamento.pagos,
    "ajuda": ajuda.ajuda,
    "help": ajuda.ajuda,
}


def handle(grupo: Grupo, msg: IncomingMessage) -> Reply | None:
    if not msg.text.startswith(PREFIX):
        return None
    partes = msg.text[len(PREFIX) :].split()
    if not partes:
        return None
    handler = _HANDLERS.get(partes[0].lower())
    if handler is None:
        return None
    return handler(montar(grupo, msg, partes[1:]))
