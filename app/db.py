"""Camada de acesso ao SQLite. Mantém o repositório de jogadores."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from .config import settings


@dataclass
class Player:
    jid: str
    phone: str
    name: str
    overall: int


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                jid        TEXT UNIQUE NOT NULL,
                phone      TEXT NOT NULL,
                name       TEXT NOT NULL,
                overall    INTEGER NOT NULL CHECK (overall BETWEEN 1 AND 10),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )


def get_player(jid: str) -> Player | None:
    with _connect() as conn:
        r = conn.execute(
            "SELECT jid, phone, name, overall FROM players WHERE jid = ?", (jid,)
        ).fetchone()
    return Player(r["jid"], r["phone"], r["name"], r["overall"]) if r else None


def upsert_player(jid: str, phone: str, name: str, overall: int) -> bool:
    """Cadastra ou atualiza um jogador. Retorna True se foi inserção nova."""
    now = int(time.time())
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM players WHERE jid = ?", (jid,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE players
                   SET phone = ?, name = ?, overall = ?, updated_at = ?
                   WHERE jid = ?""",
                (phone, name, overall, now, jid),
            )
            return False
        conn.execute(
            """INSERT INTO players (jid, phone, name, overall, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (jid, phone, name, overall, now, now),
        )
        return True


def remove_player(jid: str) -> bool:
    """Remove um jogador pelo jid. Retorna True se algo foi removido."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM players WHERE jid = ?", (jid,))
        return cur.rowcount > 0


def list_players() -> list[Player]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT jid, phone, name, overall FROM players ORDER BY overall DESC, name ASC"
        ).fetchall()
    return [Player(r["jid"], r["phone"], r["name"], r["overall"]) for r in rows]
