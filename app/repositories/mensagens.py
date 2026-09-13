"""Outbox de mensagens: o dashboard enfileira, o bot distribui por grupo e conclui."""
from __future__ import annotations

from uuid import UUID

from ..database import executar, transacao

# Filtro explícito por escopo; escopo desconhecido não tem destino (nunca "todos").
_FILTRO_POR_ESCOPO = {
    "grupo": "AND g.id = %(grupo_id)s",
    "arena": "AND g.arena_id = %(arena_id)s",
    "todos": "",
}


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


def distribuir(limite: int = 20) -> None:
    """Expande cada mensagem pendente em um envio por grupo ativo do destino."""
    with transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, escopo::text, grupo_id, arena_id
                FROM pelada.mensagens
                WHERE status = 'pendente' AND distribuida_em IS NULL
                  AND (agendar_para IS NULL OR agendar_para <= now())
                ORDER BY criado_em
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (limite,),
            )
            for mensagem_id, escopo, grupo_id, arena_id in cur.fetchall():
                filtro = _FILTRO_POR_ESCOPO.get(escopo)
                inseridos = 0 if filtro is None else executar(
                    conn,
                    """
                    INSERT INTO pelada.mensagem_envios (mensagem_id, grupo_id, wa_group_jid)
                    SELECT %(mensagem_id)s::uuid, g.id, g.wa_group_jid
                    FROM pelada.grupos g
                    WHERE g.ativo """ + filtro + """
                    ON CONFLICT (mensagem_id, grupo_id) DO NOTHING
                    """,
                    {"mensagem_id": mensagem_id, "grupo_id": grupo_id, "arena_id": arena_id},
                )
                if inseridos:
                    executar(conn, "UPDATE pelada.mensagens SET distribuida_em = now() WHERE id = %s", (mensagem_id,))
                else:
                    executar(
                        conn,
                        """
                        UPDATE pelada.mensagens
                        SET status = 'erro', erro = 'Nenhum grupo ativo no destino.', distribuida_em = now()
                        WHERE id = %s
                        """,
                        (mensagem_id,),
                    )


def concluir() -> None:
    """Fecha as mensagens distribuídas sem envio pendente: enviado se todos foram, senão erro."""
    # LEFT JOIN: se o grupo foi apagado, o cascade leva os envios e a mensagem fecharia nunca.
    with transacao() as conn:
        executar(
            conn,
            """
            UPDATE pelada.mensagens m
            SET status = (CASE WHEN r.total > 0 AND r.falhas = 0 THEN 'enviado' ELSE 'erro' END)::pelada.mensagem_status,
                erro = CASE
                    WHEN r.total = 0 THEN 'Nenhum grupo ativo no destino.'
                    WHEN r.falhas > 0 THEN left(
                        'Falhou em ' || r.falhas || ' de ' || r.total || ' grupos: ' || coalesce(r.ultimo_erro, '?'), 500
                    )
                END,
                enviado_em = CASE WHEN r.total > 0 AND r.falhas = 0 THEN now() END
            FROM (
                SELECT p.id,
                       count(e.id) AS total,
                       count(e.id) FILTER (WHERE e.status <> 'enviado') AS falhas,
                       (array_agg(e.erro ORDER BY e.proxima_tentativa DESC) FILTER (WHERE e.status = 'erro'))[1] AS ultimo_erro
                FROM pelada.mensagens p
                LEFT JOIN pelada.mensagem_envios e ON e.mensagem_id = p.id
                WHERE p.status = 'pendente' AND p.distribuida_em IS NOT NULL
                GROUP BY p.id
                HAVING count(e.id) FILTER (WHERE e.status = 'pendente') = 0
            ) r
            WHERE m.id = r.id AND m.status = 'pendente' AND m.distribuida_em IS NOT NULL
            """,
            (),
        )
