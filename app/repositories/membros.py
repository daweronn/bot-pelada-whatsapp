"""Membros de um grupo: cadastro, nota e tipo."""
from __future__ import annotations

from uuid import UUID

from ..database import buscar, executar, listar, transacao
from ..models import Membro

_COLUNAS = "id, grupo_id, identity_key, phone_jid, lid, nome, overall, mensalista"


def por_identidade(grupo_id: UUID, identidades: list[str]) -> Membro | None:
    if not identidades:
        return None
    with transacao() as conn:
        return buscar(
            conn,
            Membro,
            f"SELECT {_COLUNAS} FROM pelada.membros"
            " WHERE grupo_id = %s AND identity_key = ANY(%s) AND ativo",
            (grupo_id, identidades),
        )


def por_id(membro_id: UUID) -> Membro | None:
    with transacao() as conn:
        return buscar(
            conn, Membro, f"SELECT {_COLUNAS} FROM pelada.membros WHERE id = %s", (membro_id,)
        )


def salvar(
    grupo_id: UUID,
    identity_key: str,
    nome: str,
    overall: int,
    mensalista: bool | None = None,
    phone_jid: str | None = None,
    lid: str | None = None,
) -> tuple[Membro, bool]:
    """Cria ou atualiza. `mensalista=None` preserva o valor atual.
    Retorna (membro, criado)."""
    with transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pelada.membros WHERE grupo_id = %s AND identity_key = %s",
                (grupo_id, identity_key),
            )
            existia = cur.fetchone() is not None
        membro = buscar(
            conn,
            Membro,
            f"""
            INSERT INTO pelada.membros
                (grupo_id, identity_key, nome, overall, mensalista, phone_jid, lid)
            VALUES (%s, %s, %s, %s, COALESCE(%s, false), %s, %s)
            ON CONFLICT (grupo_id, identity_key) DO UPDATE SET
                nome = EXCLUDED.nome,
                overall = EXCLUDED.overall,
                mensalista = COALESCE(%s, pelada.membros.mensalista),
                phone_jid = COALESCE(EXCLUDED.phone_jid, pelada.membros.phone_jid),
                lid = COALESCE(EXCLUDED.lid, pelada.membros.lid),
                ativo = true
            RETURNING {_COLUNAS}
            """,
            (grupo_id, identity_key, nome, overall, mensalista, phone_jid, lid, mensalista),
        )
    return membro, not existia


def registrar_contato(
    grupo_id: UUID, identity_key: str, phone_jid: str | None, lid: str | None
) -> None:
    """Completa phone_jid/lid de quem já é membro, sem alterar nome ou nota."""
    if not phone_jid and not lid:
        return
    with transacao() as conn:
        executar(
            conn,
            """
            UPDATE pelada.membros
            SET phone_jid = COALESCE(phone_jid, %s), lid = COALESCE(lid, %s)
            WHERE grupo_id = %s AND identity_key = %s
            """,
            (phone_jid, lid, grupo_id, identity_key),
        )


def definir_mensalista(grupo_id: UUID, identity_key: str, valor: bool) -> bool:
    with transacao() as conn:
        return executar(
            conn,
            "UPDATE pelada.membros SET mensalista = %s WHERE grupo_id = %s AND identity_key = %s",
            (valor, grupo_id, identity_key),
        ) > 0


def ajustar_overall(membro_id: UUID, delta: int) -> Membro | None:
    with transacao() as conn:
        return buscar(
            conn,
            Membro,
            f"""
            UPDATE pelada.membros
            SET overall = LEAST(10, GREATEST(0, overall + %s))
            WHERE id = %s
            RETURNING {_COLUNAS}
            """,
            (delta, membro_id),
        )


def remover(grupo_id: UUID, identity_key: str) -> bool:
    with transacao() as conn:
        return executar(
            conn,
            "DELETE FROM pelada.membros WHERE grupo_id = %s AND identity_key = %s",
            (grupo_id, identity_key),
        ) > 0


def listar_todos(grupo_id: UUID) -> list[Membro]:
    with transacao() as conn:
        return listar(
            conn,
            Membro,
            f"SELECT {_COLUNAS} FROM pelada.membros WHERE grupo_id = %s AND ativo"
            " ORDER BY mensalista DESC, overall DESC, nome ASC",
            (grupo_id,),
        )


def buscar_por_nome(grupo_id: UUID, nome: str) -> list[Membro]:
    """Busca em camadas: exato sensível à caixa, exato ignorando caixa, contém."""
    nome = nome.strip()
    if not nome:
        return []
    base = f"SELECT {_COLUNAS} FROM pelada.membros WHERE grupo_id = %s AND ativo AND "
    tentativas = (
        (base + "nome = %s", nome),
        (base + "lower(nome) = lower(%s)", nome),
        (base + "nome ILIKE %s", f"%{nome}%"),
    )
    with transacao() as conn:
        for sql, parametro in tentativas:
            encontrados = listar(conn, Membro, sql, (grupo_id, parametro))
            if encontrados:
                return encontrados
    return []
