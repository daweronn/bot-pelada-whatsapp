"""Votações de MVP e Bagre, sempre atreladas a uma rodada."""
from __future__ import annotations

from uuid import UUID

from ..database import buscar, executar, listar, transacao
from ..models import ResultadoVoto, Votacao

_COLUNAS = "id, rodada_id, tipo, aberta"


def por_tipo(rodada_id: UUID, tipo: str) -> Votacao | None:
    with transacao() as conn:
        return buscar(
            conn,
            Votacao,
            f"SELECT {_COLUNAS} FROM pelada.votacoes WHERE rodada_id = %s AND tipo = %s",
            (rodada_id, tipo),
        )


def abrir(rodada_id: UUID, tipo: str) -> Votacao:
    with transacao() as conn:
        votacao = buscar(
            conn,
            Votacao,
            f"""
            INSERT INTO pelada.votacoes (rodada_id, tipo) VALUES (%s, %s)
            ON CONFLICT (rodada_id, tipo) DO UPDATE SET aberta = true
            RETURNING {_COLUNAS}
            """,
            (rodada_id, tipo),
        )
        executar(conn, "DELETE FROM pelada.votos WHERE votacao_id = %s", (votacao.id,))
    return votacao


def votar(votacao_id: UUID, votante_id: UUID, candidato_id: UUID) -> bool:
    """Registra ou troca o voto. True quando substituiu um voto anterior."""
    with transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pelada.votos WHERE votacao_id = %s AND votante_id = %s",
                (votacao_id, votante_id),
            )
            existia = cur.fetchone() is not None
        executar(
            conn,
            """
            INSERT INTO pelada.votos (votacao_id, votante_id, candidato_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (votacao_id, votante_id) DO UPDATE
                SET candidato_id = EXCLUDED.candidato_id, created_at = now()
            """,
            (votacao_id, votante_id, candidato_id),
        )
    return existia


def fechar(votacao_id: UUID) -> list[ResultadoVoto]:
    with transacao() as conn:
        executar(conn, "UPDATE pelada.votacoes SET aberta = false WHERE id = %s", (votacao_id,))
        return listar(
            conn,
            ResultadoVoto,
            """
            SELECT m.id AS membro_id, m.nome, m.phone_jid, m.lid, m.overall,
                   COUNT(*)::int AS votos
            FROM pelada.votos v
            JOIN pelada.membros m ON m.id = v.candidato_id
            WHERE v.votacao_id = %s
            GROUP BY m.id, m.nome, m.phone_jid, m.lid, m.overall
            ORDER BY votos DESC, m.nome ASC
            """,
            (votacao_id,),
        )
