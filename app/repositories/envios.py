"""Envios da fila: um por (mensagem, grupo), reservados um de cada vez com lease."""
from __future__ import annotations

from uuid import UUID

from ..database import buscar, executar, transacao
from ..models import Envio


def reservar_proximo(lease_s: int, mensagem_id: UUID | None = None) -> Envio | None:
    """Reserva o próximo envio vencido (só da mensagem dada, se houver); o lease trava outras instâncias."""
    with transacao() as conn:
        return buscar(
            conn,
            Envio,
            """
            UPDATE pelada.mensagem_envios e
            SET tentativas = e.tentativas + 1, proxima_tentativa = now() + make_interval(secs => %(lease_s)s)
            FROM pelada.mensagens m
            WHERE m.id = e.mensagem_id AND e.id = (
                SELECT id FROM pelada.mensagem_envios
                WHERE status = 'pendente' AND proxima_tentativa <= now()
                  AND (%(mensagem_id)s::uuid IS NULL OR mensagem_id = %(mensagem_id)s::uuid)
                ORDER BY proxima_tentativa, criado_em
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING e.id, e.mensagem_id, e.wa_group_jid, e.tentativas, m.texto
            """,
            {"lease_s": lease_s, "mensagem_id": mensagem_id},
        )


def marcar_enviado(envio_id: UUID) -> None:
    with transacao() as conn:
        executar(
            conn,
            "UPDATE pelada.mensagem_envios SET status = 'enviado', enviado_em = now(), erro = NULL WHERE id = %s",
            (envio_id,),
        )


def reagendar(envio_id: UUID, erro: str, espera_s: float) -> None:
    with transacao() as conn:
        executar(
            conn,
            """
            UPDATE pelada.mensagem_envios
            SET erro = %s, proxima_tentativa = now() + make_interval(secs => %s)
            WHERE id = %s
            """,
            (erro[:500], espera_s, envio_id),
        )


def marcar_erro(envio_id: UUID, erro: str) -> None:
    with transacao() as conn:
        executar(
            conn,
            "UPDATE pelada.mensagem_envios SET status = 'erro', erro = %s WHERE id = %s",
            (erro[:500], envio_id),
        )
