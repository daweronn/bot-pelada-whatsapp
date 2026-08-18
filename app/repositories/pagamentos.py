"""Mensalidades: config por grupo e ledger mensal (competência = mês corrente)."""
from __future__ import annotations

from uuid import UUID

from ..database import buscar, executar, listar, transacao
from ..models import Membro, PagamentoConfig

_COMP = "date_trunc('month', current_date)::date"
_MEMBRO = "m.id, m.grupo_id, m.identity_key, m.phone_jid, m.lid, m.nome, m.overall, m.mensalista"


def config(grupo_id: UUID) -> PagamentoConfig | None:
    with transacao() as conn:
        return buscar(
            conn,
            PagamentoConfig,
            "SELECT valor, dia_vencimento, pix_chave, ativo FROM pelada.pagamento_config WHERE grupo_id = %s",
            (grupo_id,),
        )


def marcar(grupo_id: UUID, membro_id: UUID, status: str) -> None:
    with transacao() as conn:
        executar(
            conn,
            f"""
            INSERT INTO pelada.pagamentos (grupo_id, membro_id, competencia, status, valor)
            SELECT %s, %s, {_COMP}, %s::pelada.pagamento_status,
                   (SELECT valor FROM pelada.pagamento_config WHERE grupo_id = %s)
            ON CONFLICT (grupo_id, membro_id, competencia) DO UPDATE SET
                status = EXCLUDED.status, valor = EXCLUDED.valor, pago_em = now()
            """,
            (grupo_id, membro_id, status, grupo_id),
        )


def remover(grupo_id: UUID, membro_id: UUID) -> bool:
    with transacao() as conn:
        return executar(
            conn,
            f"DELETE FROM pelada.pagamentos WHERE grupo_id = %s AND membro_id = %s AND competencia = {_COMP}",
            (grupo_id, membro_id),
        ) > 0


def devedores(grupo_id: UUID) -> list[Membro]:
    with transacao() as conn:
        return listar(
            conn,
            Membro,
            f"""
            SELECT {_MEMBRO} FROM pelada.membros m
            WHERE m.grupo_id = %s AND m.ativo AND m.mensalista
              AND NOT EXISTS (
                SELECT 1 FROM pelada.pagamentos p WHERE p.membro_id = m.id AND p.competencia = {_COMP}
              )
            ORDER BY m.nome
            """,
            (grupo_id,),
        )


def pagantes(grupo_id: UUID) -> list[Membro]:
    with transacao() as conn:
        return listar(
            conn,
            Membro,
            f"""
            SELECT {_MEMBRO} FROM pelada.membros m
            JOIN pelada.pagamentos p ON p.membro_id = m.id AND p.competencia = {_COMP}
            WHERE m.grupo_id = %s AND m.ativo
            ORDER BY m.nome
            """,
            (grupo_id,),
        )
