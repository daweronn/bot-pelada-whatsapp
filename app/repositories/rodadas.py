"""Rodadas (cada pelada realizada) e as presenças confirmadas nelas."""
from __future__ import annotations

from uuid import UUID

from ..database import buscar, executar, listar, transacao
from ..models import Presenca, Rodada

_COLUNAS = "id, grupo_id, data, vagas, status"


def aberta(grupo_id: UUID) -> Rodada | None:
    with transacao() as conn:
        return buscar(
            conn,
            Rodada,
            f"SELECT {_COLUNAS} FROM pelada.rodadas"
            " WHERE grupo_id = %s AND status = 'aberta'",
            (grupo_id,),
        )


def corrente(grupo_id: UUID) -> Rodada | None:
    """A rodada aberta, ou a última fechada — é sobre ela que sorteio e votação agem."""
    with transacao() as conn:
        return buscar(
            conn,
            Rodada,
            f"SELECT {_COLUNAS} FROM pelada.rodadas"
            " WHERE grupo_id = %s AND status <> 'finalizada'"
            " ORDER BY status = 'aberta' DESC, created_at DESC LIMIT 1",
            (grupo_id,),
        )


def abrir(grupo_id: UUID, vagas: int) -> tuple[Rodada, int]:
    """Finaliza a rodada anterior, abre uma nova e já inclui os mensalistas.
    Retorna (rodada, mensalistas incluídos)."""
    with transacao() as conn:
        executar(
            conn,
            "UPDATE pelada.rodadas SET status = 'finalizada'"
            " WHERE grupo_id = %s AND status <> 'finalizada'",
            (grupo_id,),
        )
        rodada = buscar(
            conn,
            Rodada,
            f"INSERT INTO pelada.rodadas (grupo_id, vagas) VALUES (%s, %s) RETURNING {_COLUNAS}",
            (grupo_id, vagas),
        )
        incluidos = executar(
            conn,
            """
            INSERT INTO pelada.presencas (rodada_id, membro_id, ordem)
            SELECT %s, id, row_number() OVER (ORDER BY overall DESC, nome ASC)
            FROM pelada.membros
            WHERE grupo_id = %s AND ativo AND mensalista
            """,
            (rodada.id, grupo_id),
        )
    return rodada, incluidos


def fechar(rodada_id: UUID) -> None:
    with transacao() as conn:
        executar(
            conn, "UPDATE pelada.rodadas SET status = 'fechada' WHERE id = %s", (rodada_id,)
        )


def confirmar(rodada_id: UUID, membro_id: UUID) -> bool:
    """Adiciona na próxima posição. False se já estava confirmado."""
    with transacao() as conn:
        return executar(
            conn,
            """
            INSERT INTO pelada.presencas (rodada_id, membro_id, ordem)
            SELECT %s, %s, COALESCE(MAX(ordem), 0) + 1
            FROM pelada.presencas WHERE rodada_id = %s
            ON CONFLICT (rodada_id, membro_id) DO NOTHING
            """,
            (rodada_id, membro_id, rodada_id),
        ) > 0


def cancelar(rodada_id: UUID, membro_id: UUID) -> bool:
    with transacao() as conn:
        return executar(
            conn,
            "DELETE FROM pelada.presencas WHERE rodada_id = %s AND membro_id = %s",
            (rodada_id, membro_id),
        ) > 0


def presencas(rodada_id: UUID) -> list[Presenca]:
    with transacao() as conn:
        return listar(
            conn,
            Presenca,
            """
            SELECT m.id AS membro_id, m.identity_key, m.phone_jid, m.lid,
                   m.nome, m.overall, m.mensalista, p.ordem
            FROM pelada.presencas p
            JOIN pelada.membros m ON m.id = p.membro_id
            WHERE p.rodada_id = %s
            ORDER BY p.ordem ASC
            """,
            (rodada_id,),
        )


def separar(lista: list[Presenca], vagas: int) -> tuple[list[Presenca], list[Presenca]]:
    """Mensalista tem prioridade de titular; o resto entra por ordem de chegada."""
    ordenado = sorted(lista, key=lambda p: (0 if p.mensalista else 1, p.ordem))
    return ordenado[:vagas], ordenado[vagas:]
