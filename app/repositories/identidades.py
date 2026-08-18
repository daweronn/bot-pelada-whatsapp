"""Vínculo global LID <-> telefone e fusão de membros duplicados.

O par LID/telefone é fato do WhatsApp, não do tenant: vale para todos os
grupos. A fusão, ao contrário, acontece dentro de cada grupo.
"""
from __future__ import annotations

from psycopg import Connection

from ..database import executar, transacao


def vincular(lid: str, phone_key: str) -> None:
    if not lid or not phone_key or lid == phone_key:
        return
    with transacao() as conn:
        executar(
            conn,
            """
            INSERT INTO pelada.identity_links (lid, phone_key)
            VALUES (%s, %s)
            ON CONFLICT (lid) DO UPDATE
                SET phone_key = EXCLUDED.phone_key, updated_at = now()
            """,
            (lid, phone_key),
        )
        _fundir_membros(conn, lid, phone_key)


def resolver(identity_key: str) -> str:
    if not identity_key:
        return identity_key
    with transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT phone_key FROM pelada.identity_links WHERE lid = %s",
                (identity_key,),
            )
            linha = cur.fetchone()
    return linha[0] if linha else identity_key


def resolver_varias(identidades: list[str]) -> list[str]:
    resolvidas: list[str] = []
    for identidade in identidades:
        for chave in (resolver(identidade), identidade):
            if chave and chave not in resolvidas:
                resolvidas.append(chave)
    return resolvidas


def _fundir_membros(conn: Connection, chave_antiga: str, chave_nova: str) -> None:
    """Em cada grupo onde as duas chaves coexistem, mantém a do telefone."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT antigo.id, novo.id
            FROM pelada.membros antigo
            JOIN pelada.membros novo
              ON novo.grupo_id = antigo.grupo_id AND novo.identity_key = %s
            WHERE antigo.identity_key = %s
            """,
            (chave_nova, chave_antiga),
        )
        colisoes = cur.fetchall()

    for id_antigo, id_novo in colisoes:
        executar(
            conn,
            """
            UPDATE pelada.membros novo SET
                nome = CASE WHEN novo.nome LIKE 'Jogador %%' AND antigo.nome NOT LIKE 'Jogador %%'
                            THEN antigo.nome ELSE novo.nome END,
                mensalista = novo.mensalista OR antigo.mensalista,
                phone_jid = COALESCE(novo.phone_jid, antigo.phone_jid),
                lid = COALESCE(novo.lid, antigo.lid)
            FROM pelada.membros antigo
            WHERE novo.id = %s AND antigo.id = %s
            """,
            (id_novo, id_antigo),
        )
        executar(
            conn,
            "UPDATE pelada.presencas SET membro_id = %s WHERE membro_id = %s"
            " AND rodada_id NOT IN (SELECT rodada_id FROM pelada.presencas WHERE membro_id = %s)",
            (id_novo, id_antigo, id_novo),
        )
        executar(conn, "DELETE FROM pelada.membros WHERE id = %s", (id_antigo,))

    executar(
        conn,
        """
        UPDATE pelada.membros
        SET identity_key = %s, lid = COALESCE(lid, %s)
        WHERE identity_key = %s
        """,
        (chave_nova, chave_antiga, chave_antiga),
    )
