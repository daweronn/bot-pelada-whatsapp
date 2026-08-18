"""Grupos atendidos (tenant) e seus administradores."""
from __future__ import annotations

from uuid import UUID

from ..database import buscar, transacao
from ..models import Grupo


def por_jid(wa_group_jid: str) -> Grupo | None:
    """Grupo ativo correspondente ao remoteJid. None = grupo não atendido."""
    with transacao() as conn:
        return buscar(
            conn,
            Grupo,
            """
            SELECT id, wa_group_jid, nome, vagas_padrao, principal
            FROM pelada.grupos
            WHERE wa_group_jid = %s AND ativo
            """,
            (wa_group_jid,),
        )


def e_admin(grupo_id: UUID, identidades: list[str]) -> bool:
    if not identidades:
        return False
    with transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM pelada.admins
                WHERE grupo_id = %s AND identity_key = ANY(%s)
                LIMIT 1
                """,
                (grupo_id, identidades),
            )
            return cur.fetchone() is not None
