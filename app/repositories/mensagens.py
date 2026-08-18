"""Outbox de mensagens: o dashboard enfileira, o bot envia."""
from __future__ import annotations

from uuid import UUID

from ..database import executar, listar, transacao
from ..models import MensagemFila


def enfileirar(escopo: str, texto: str, grupo_id: UUID | None = None, arena_id: UUID | None = None) -> None:
    with transacao() as conn:
        executar(
            conn,
            """
            INSERT INTO pelada.mensagens (escopo, grupo_id, arena_id, tipo, texto)
            VALUES (%s, %s, %s, 'noticia', %s)
            """,
            (escopo, grupo_id, arena_id, texto),
        )


def pendentes(limite: int = 20) -> list[MensagemFila]:
    with transacao() as conn:
        return listar(
            conn,
            MensagemFila,
            """
            SELECT id, escopo::text AS escopo, grupo_id, arena_id, texto
            FROM pelada.mensagens
            WHERE status = 'pendente' AND (agendar_para IS NULL OR agendar_para <= now())
            ORDER BY criado_em ASC
            LIMIT %s
            """,
            (limite,),
        )


def destinos(msg: MensagemFila) -> list[str]:
    with transacao() as conn:
        with conn.cursor() as cur:
            if msg.escopo == "grupo":
                cur.execute("SELECT wa_group_jid FROM pelada.grupos WHERE id = %s AND ativo", (msg.grupo_id,))
            elif msg.escopo == "arena":
                cur.execute("SELECT wa_group_jid FROM pelada.grupos WHERE arena_id = %s AND ativo", (msg.arena_id,))
            else:
                cur.execute("SELECT wa_group_jid FROM pelada.grupos WHERE ativo")
            return [linha[0] for linha in cur.fetchall()]


def marcar_enviado(mensagem_id: UUID) -> None:
    with transacao() as conn:
        executar(
            conn,
            "UPDATE pelada.mensagens SET status = 'enviado', enviado_em = now() WHERE id = %s",
            (mensagem_id,),
        )


def marcar_erro(mensagem_id: UUID, erro: str) -> None:
    with transacao() as conn:
        executar(
            conn,
            "UPDATE pelada.mensagens SET status = 'erro', tentativas = tentativas + 1, erro = %s WHERE id = %s",
            (erro[:500], mensagem_id),
        )
