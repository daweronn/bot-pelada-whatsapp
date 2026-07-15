"""Camada de acesso ao SQLite: jogadores, mensalistas e a lista da pelada."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from .config import settings


@dataclass
class Player:
    phone: str          # chave canônica (55+DDD+8)
    name: str
    overall: int
    mensalista: bool
    pagou: bool = False


@dataclass
class ListaEntry:
    player: Player
    ordem: int          # ordem de chegada na lista


@dataclass
class VoteResult:
    player: Player
    votes: int
    jid: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                phone      TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                overall    INTEGER NOT NULL CHECK (overall BETWEEN 0 AND 10),
                mensalista INTEGER NOT NULL DEFAULT 0,
                pagou      INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lista_entries (
                phone      TEXT PRIMARY KEY,
                ordem      INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS lista_state (id INTEGER PRIMARY KEY CHECK (id = 1), aberta INTEGER NOT NULL, vagas INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO lista_state (id, aberta, vagas) VALUES (1, 0, 15)"
        )
        # migração: coluna de pagamento (sem perder dados existentes)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(players)")]
        if "pagou" not in cols:
            conn.execute("ALTER TABLE players ADD COLUMN pagou INTEGER NOT NULL DEFAULT 0")
        _migrate_overall_zero(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vote_state (
                kind       TEXT PRIMARY KEY CHECK (kind IN ('mvp', 'bagre')),
                aberta     INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT OR IGNORE INTO vote_state (kind, aberta, created_at) VALUES (?, 0, ?)",
            [("mvp", int(time.time())), ("bagre", int(time.time()))],
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                kind            TEXT NOT NULL CHECK (kind IN ('mvp', 'bagre')),
                voter_phone     TEXT NOT NULL,
                candidate_phone TEXT NOT NULL,
                candidate_jid   TEXT NOT NULL,
                created_at      INTEGER NOT NULL,
                PRIMARY KEY (kind, voter_phone)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS identity_links (
                lid        TEXT PRIMARY KEY,
                phone      TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )


def _migrate_overall_zero(conn: sqlite3.Connection) -> None:
    """Troca o CHECK antigo (1..10) por 0..10 sem perder jogadores."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'players'"
    ).fetchone()
    sql = (row["sql"] or "").replace(" ", "").lower() if row else ""
    if "between1and10" not in sql:
        return
    conn.execute("ALTER TABLE players RENAME TO players_old")
    conn.execute(
        """
        CREATE TABLE players (
            phone      TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            overall    INTEGER NOT NULL CHECK (overall BETWEEN 0 AND 10),
            mensalista INTEGER NOT NULL DEFAULT 0,
            pagou      INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO players (phone, name, overall, mensalista, pagou, created_at, updated_at)
        SELECT phone, name, overall, mensalista, pagou, created_at, updated_at
        FROM players_old
        """
    )
    conn.execute("DROP TABLE players_old")


# ------------------------------------------------------------- identidade ----
def placeholder_name(ident: str) -> str:
    return f"Jogador {ident[-5:]}"


def is_placeholder_name(name: str) -> bool:
    return name.startswith("Jogador ")


def link_identity(lid: str, phone: str) -> None:
    """Aprende que o LID e o telefone são a mesma pessoa; funde cadastros duplicados."""
    if not lid or not phone or lid == phone:
        return
    now = int(time.time())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO identity_links (lid, phone, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(lid) DO UPDATE SET phone = excluded.phone, updated_at = excluded.updated_at
            """,
            (lid, phone, now),
        )
        _merge_player_keys(conn, lid, phone)


def resolve_identity(ident: str) -> str:
    """Se o identificador for um LID já vinculado, devolve o telefone real."""
    if not ident:
        return ident
    with _connect() as conn:
        row = conn.execute(
            "SELECT phone FROM identity_links WHERE lid = ?", (ident,)
        ).fetchone()
    return row["phone"] if row else ident


def _merge_player_keys(conn: sqlite3.Connection, old_key: str, new_key: str) -> None:
    """Migra tudo que estava sob a chave antiga (LID) pra chave nova (telefone)."""
    old = conn.execute("SELECT * FROM players WHERE phone = ?", (old_key,)).fetchone()
    if old:
        now = int(time.time())
        new = conn.execute("SELECT * FROM players WHERE phone = ?", (new_key,)).fetchone()
        if new is None:
            conn.execute(
                "UPDATE players SET phone = ?, updated_at = ? WHERE phone = ?",
                (new_key, now, old_key),
            )
        else:
            name = (
                old["name"]
                if is_placeholder_name(new["name"]) and not is_placeholder_name(old["name"])
                else new["name"]
            )
            conn.execute(
                "UPDATE players SET name = ?, mensalista = ?, pagou = ?, updated_at = ? WHERE phone = ?",
                (
                    name,
                    new["mensalista"] or old["mensalista"],
                    new["pagou"] or old["pagou"],
                    now,
                    new_key,
                ),
            )
            conn.execute("DELETE FROM players WHERE phone = ?", (old_key,))
    conn.execute(
        "UPDATE OR IGNORE lista_entries SET phone = ? WHERE phone = ?", (new_key, old_key)
    )
    conn.execute("DELETE FROM lista_entries WHERE phone = ?", (old_key,))
    conn.execute(
        "UPDATE OR IGNORE votes SET voter_phone = ? WHERE voter_phone = ?", (new_key, old_key)
    )
    conn.execute("DELETE FROM votes WHERE voter_phone = ?", (old_key,))
    conn.execute(
        "UPDATE votes SET candidate_phone = ? WHERE candidate_phone = ?", (new_key, old_key)
    )


# ---------------------------------------------------------------- players ----
def _row_to_player(r: sqlite3.Row) -> Player:
    return Player(r["phone"], r["name"], r["overall"], bool(r["mensalista"]), bool(r["pagou"]))


def get_player(phone: str) -> Player | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT phone, name, overall, mensalista, pagou FROM players WHERE phone = ?",
            (phone,),
        ).fetchone()
    return _row_to_player(r) if r else None


def upsert_player(phone: str, name: str, overall: int, mensalista: bool | None = None) -> bool:
    """Cadastra/atualiza. `mensalista=None` mantém o valor atual. Retorna True se novo."""
    now = int(time.time())
    with _connect() as conn:
        existing = conn.execute(
            "SELECT mensalista FROM players WHERE phone = ?", (phone,)
        ).fetchone()
        if existing:
            mens = existing["mensalista"] if mensalista is None else int(mensalista)
            conn.execute(
                "UPDATE players SET name = ?, overall = ?, mensalista = ?, updated_at = ? WHERE phone = ?",
                (name, overall, mens, now, phone),
            )
            return False
        conn.execute(
            "INSERT INTO players (phone, name, overall, mensalista, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (phone, name, overall, int(bool(mensalista)), now, now),
        )
        return True


def set_mensalista(phone: str, value: bool) -> bool:
    """Marca/desmarca mensalista. Retorna False se o jogador não existe."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE players SET mensalista = ?, updated_at = ? WHERE phone = ?",
            (int(value), int(time.time()), phone),
        )
        return cur.rowcount > 0


def set_pagou(phone: str, value: bool) -> bool:
    """Marca/desmarca pagamento. Retorna False se o jogador não existe."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE players SET pagou = ?, updated_at = ? WHERE phone = ?",
            (int(value), int(time.time()), phone),
        )
        return cur.rowcount > 0


def adjust_overall(phone: str, delta: int) -> Player | None:
    """Soma ou subtrai overall, sempre mantendo o resultado entre 0 e 10."""
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE players
            SET overall = MIN(10, MAX(0, overall + ?)), updated_at = ?
            WHERE phone = ?
            """,
            (delta, int(time.time()), phone),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT phone, name, overall, mensalista, pagou FROM players WHERE phone = ?",
            (phone,),
        ).fetchone()
    return _row_to_player(row)


def reset_pagamentos() -> int:
    """Zera o pagamento de todo mundo. Retorna quantos estavam marcados como pagos."""
    with _connect() as conn:
        pagos = conn.execute("SELECT COUNT(*) AS n FROM players WHERE pagou = 1").fetchone()["n"]
        conn.execute("UPDATE players SET pagou = 0, updated_at = ?", (int(time.time()),))
    return pagos


def remove_player(phone: str) -> bool:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM votes WHERE voter_phone = ? OR candidate_phone = ?",
            (phone, phone),
        )
        conn.execute("DELETE FROM lista_entries WHERE phone = ?", (phone,))
        cur = conn.execute("DELETE FROM players WHERE phone = ?", (phone,))
        return cur.rowcount > 0


def list_players() -> list[Player]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT phone, name, overall, mensalista, pagou FROM players ORDER BY mensalista DESC, overall DESC, name ASC"
        ).fetchall()
    return [_row_to_player(r) for r in rows]


def find_players_by_name(name: str) -> list[Player]:
    """Busca por nome em camadas, da mais precisa para a mais ampla:
    1) exato com maiúsculas/minúsculas (Nathan ≠ nathan)
    2) exato ignorando caixa
    3) 'contém'
    Retorna a primeira camada que achar algo."""
    name = name.strip()
    if not name:
        return []
    sel = "SELECT phone, name, overall, mensalista, pagou FROM players "
    tentativas = [
        (sel + "WHERE name = ?", (name,)),                          # exato, sensível à caixa
        (sel + "WHERE name = ? COLLATE NOCASE", (name,)),           # exato, ignora caixa
        (sel + "WHERE name LIKE ? COLLATE NOCASE", (f"%{name}%",)),  # contém
    ]
    with _connect() as conn:
        for query, params in tentativas:
            rows = conn.execute(query, params).fetchall()
            if rows:
                return [_row_to_player(r) for r in rows]
    return []


# ------------------------------------------------------------------ lista ----
def lista_state() -> tuple[bool, int]:
    with _connect() as conn:
        r = conn.execute("SELECT aberta, vagas FROM lista_state WHERE id = 1").fetchone()
    return (bool(r["aberta"]), r["vagas"]) if r else (False, 10)


def open_lista(vagas: int) -> int:
    """Abre a lista (zera a anterior) e já pré-inclui os mensalistas como titulares.
    Retorna quantos mensalistas foram incluídos."""
    now = int(time.time())
    with _connect() as conn:
        conn.execute("UPDATE vote_state SET aberta = 0")
        conn.execute("DELETE FROM votes")
        conn.execute("DELETE FROM lista_entries")
        conn.execute("UPDATE lista_state SET aberta = 1, vagas = ? WHERE id = 1", (vagas,))
        mensalistas = conn.execute(
            "SELECT phone FROM players WHERE mensalista = 1 ORDER BY overall DESC, name ASC"
        ).fetchall()
        for i, r in enumerate(mensalistas, 1):
            conn.execute(
                "INSERT INTO lista_entries (phone, ordem, created_at) VALUES (?, ?, ?)",
                (r["phone"], i, now),
            )
    return len(mensalistas)


def close_lista() -> None:
    with _connect() as conn:
        conn.execute("UPDATE lista_state SET aberta = 0 WHERE id = 1")


def add_to_lista(phone: str) -> bool:
    """Adiciona o jogador na próxima posição. Retorna False se já estava na lista."""
    now = int(time.time())
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM lista_entries WHERE phone = ?", (phone,)
        ).fetchone()
        if exists:
            return False
        nxt = conn.execute(
            "SELECT COALESCE(MAX(ordem), 0) + 1 AS n FROM lista_entries"
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO lista_entries (phone, ordem, created_at) VALUES (?, ?, ?)",
            (phone, nxt, now),
        )
        return True


def remove_from_lista(phone: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM lista_entries WHERE phone = ?", (phone,))
        return cur.rowcount > 0


def lista_entries() -> list[ListaEntry]:
    """Entradas da lista, em ordem de chegada (join com players)."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.phone, p.name, p.overall, p.mensalista, p.pagou, e.ordem
            FROM lista_entries e
            JOIN players p ON p.phone = e.phone
            ORDER BY e.ordem ASC
            """
        ).fetchall()
    return [
        ListaEntry(
            Player(r["phone"], r["name"], r["overall"], bool(r["mensalista"]), bool(r["pagou"])),
            r["ordem"],
        )
        for r in rows
    ]


# --------------------------------------------------------------- votações ----
def vote_is_open(kind: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT aberta FROM vote_state WHERE kind = ?", (kind,)
        ).fetchone()
    return bool(row["aberta"]) if row else False


def open_vote(kind: str) -> None:
    now = int(time.time())
    with _connect() as conn:
        conn.execute("DELETE FROM votes WHERE kind = ?", (kind,))
        conn.execute(
            "UPDATE vote_state SET aberta = 1, created_at = ? WHERE kind = ?",
            (now, kind),
        )


def cast_vote(
    kind: str,
    voter_phone: str,
    candidate_phone: str,
    candidate_jid: str,
) -> bool:
    """Registra ou troca um voto. Retorna True quando substituiu voto anterior."""
    now = int(time.time())
    with _connect() as conn:
        existed = conn.execute(
            "SELECT 1 FROM votes WHERE kind = ? AND voter_phone = ?",
            (kind, voter_phone),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO votes (kind, voter_phone, candidate_phone, candidate_jid, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(kind, voter_phone) DO UPDATE SET
                candidate_phone = excluded.candidate_phone,
                candidate_jid = excluded.candidate_jid,
                created_at = excluded.created_at
            """,
            (kind, voter_phone, candidate_phone, candidate_jid, now),
        )
    return existed is not None


def close_vote(kind: str) -> list[VoteResult]:
    """Fecha e devolve o placar em ordem decrescente de votos."""
    with _connect() as conn:
        conn.execute("UPDATE vote_state SET aberta = 0 WHERE kind = ?", (kind,))
        rows = conn.execute(
            """
            SELECT p.phone, p.name, p.overall, p.mensalista, p.pagou,
                   COUNT(*) AS votes, MAX(v.candidate_jid) AS jid
            FROM votes v
            JOIN players p ON p.phone = v.candidate_phone
            WHERE v.kind = ?
            GROUP BY p.phone, p.name, p.overall, p.mensalista, p.pagou
            ORDER BY votes DESC, p.name ASC
            """,
            (kind,),
        ).fetchall()
    return [
        VoteResult(_row_to_player(row), row["votes"], row["jid"])
        for row in rows
    ]
