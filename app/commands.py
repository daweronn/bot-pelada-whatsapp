"""Interpretação e execução dos comandos do bot."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import db, teams
from .config import settings
from .messages import IncomingMessage
from .phones import canonical_phone, only_digits

PREFIX = "."


@dataclass
class Reply:
    text: str
    mentions: list[str] = field(default_factory=list)


# ------------------------------------------------------------- utilidades ----
def _is_admin(msg: IncomingMessage) -> bool:
    return msg.from_me or settings.is_admin(msg.sender_phone)


def _extract_phone(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Acha o 1º token que pareça telefone (>=10 dígitos) e o canoniza."""
    for i, tok in enumerate(tokens):
        if len(only_digits(tok)) >= 10:
            rest = tokens[:i] + tokens[i + 1 :]
            return canonical_phone(tok), rest
    return None, tokens


def _extract_overall(tokens: list[str]) -> tuple[int | None, list[str]]:
    for i, tok in enumerate(tokens):
        if tok.isdigit() and 1 <= int(tok) <= 10:
            return int(tok), tokens[:i] + tokens[i + 1 :]
    return None, tokens


def _join_name(tokens: list[str]) -> str:
    return " ".join(t for t in tokens if t != "-").strip()


# --------------------------------------------------------------- cadastro ----
_EX_CAD = "Ex.: *.cadastro 5522998720569 7 João Marcelo*"


def _cmd_cadastro(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode cadastrar jogadores.")

    phone, rest = _extract_phone(args)
    if not phone:
        return Reply("❓ Faltou o *número* (com DDD).\n" + _EX_CAD)
    overall, rest = _extract_overall(rest)
    if overall is None:
        return Reply("❓ Faltou a *nota* (1 a 10).\n" + _EX_CAD)
    name = _join_name(rest)
    if not name:
        existing = db.get_player(phone)
        if existing:
            name = existing.name  # atualização só da nota mantém o nome
        else:
            return Reply("❓ Faltou o *nome*.\n" + _EX_CAD)

    is_new = db.upsert_player(phone, name, overall)
    verbo = "cadastrado" if is_new else "atualizado"
    return Reply(f"✅ *{name}* {verbo} — overall *{overall}*.")


def _cmd_remover(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode remover jogadores.")
    phone, _ = _extract_phone(args)
    if not phone:
        return Reply("❓ Use: *.remover 5522998720569*")
    return Reply("🗑️ Jogador removido." if db.remove_player(phone) else "ℹ️ Não estava cadastrado.")


def _cmd_mensalista(msg: IncomingMessage, args: list[str], value: bool) -> Reply:
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode fazer isso.")
    phone, _ = _extract_phone(args)
    if not phone:
        return Reply("❓ Use: *.mensalista 5522998720569*")
    if not db.set_mensalista(phone, value):
        return Reply("❓ Esse número não está cadastrado. Cadastre antes com *.cadastro*.")
    tipo = "mensalista" if value else "diarista"
    return Reply(f"✅ Agora é *{tipo}*.")


def _cmd_jogadores(_msg: IncomingMessage, _args: list[str]) -> Reply:
    players = db.list_players()
    if not players:
        return Reply("📋 Nenhum jogador cadastrado ainda.")
    linhas = [f"📋 *Jogadores ({len(players)})*", ""]
    for p in players:
        tag = "⭐" if p.mensalista else "•"
        linhas.append(f"{tag} {p.name} — *{p.overall}*")
    linhas.append("\n⭐ = mensalista")
    return Reply("\n".join(linhas))


# ------------------------------------------------------------------ lista ----
def _cmd_abrirlista(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode abrir a lista.")
    vagas = 10
    for tok in args:
        if tok.isdigit():
            vagas = int(tok)
            break
    db.open_lista(vagas)
    return Reply(
        f"🟢 *Lista aberta!* {vagas} vagas.\n"
        "Mande *.vou* pra confirmar presença.\n"
        "Veja a lista com *.lista*."
    )


def _cmd_fecharlista(msg: IncomingMessage, _args: list[str]) -> Reply:
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode fechar a lista.")
    db.close_lista()
    return Reply("🔴 *Lista fechada.* Use *.sorteiotimes* pra montar os times.")


def _entrar(phone: str) -> bool:
    return db.add_to_lista(phone)


def _cmd_vou(msg: IncomingMessage, _args: list[str]) -> Reply:
    aberta, _ = db.lista_state()
    if not aberta:
        return Reply("⚠️ Não tem lista aberta no momento.")
    phone = canonical_phone(msg.sender_phone)
    player = db.get_player(phone)
    if player is None:
        # diarista sem cadastro: entra com nota média e o nome do WhatsApp
        nome = msg.sender_name.strip() or "Diarista"
        db.upsert_player(phone, nome, settings.default_overall, mensalista=False)
        novo = True
    else:
        novo = False
    if not _entrar(phone):
        return Reply("✅ Você já está na lista.")
    extra = f" (cadastrado como diarista, nota {settings.default_overall})" if novo else ""
    return _render_lista(prefixo=f"✅ Presença confirmada{extra}!\n\n")


def _cmd_naovou(msg: IncomingMessage, _args: list[str]) -> Reply:
    phone = canonical_phone(msg.sender_phone)
    if db.remove_from_lista(phone):
        return _render_lista(prefixo="✅ Você saiu da lista.\n\n")
    return Reply("ℹ️ Você não estava na lista.")


def _cmd_vai(msg: IncomingMessage, args: list[str]) -> Reply:
    """Admin: cadastra (ou atualiza) e já coloca na lista."""
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode usar o *.vai*.")
    aberta, _ = db.lista_state()
    if not aberta:
        return Reply("⚠️ Abra a lista antes com *.abrirlista*.")
    phone, rest = _extract_phone(args)
    if not phone:
        return Reply("❓ Use: *.vai 5522998720569 7 João*")
    overall, rest = _extract_overall(rest)
    name = _join_name(rest)
    existing = db.get_player(phone)
    if overall is None:
        overall = existing.overall if existing else settings.default_overall
    if not name:
        name = existing.name if existing else "Diarista"
    db.upsert_player(phone, name, overall)
    db.add_to_lista(phone)
    return _render_lista(prefixo=f"✅ *{name}* na lista (overall {overall}).\n\n")


def _cmd_tira(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return Reply("🚫 Só o admin pode tirar da lista.")
    phone, _ = _extract_phone(args)
    if not phone:
        return Reply("❓ Use: *.tira 5522998720569*")
    if db.remove_from_lista(phone):
        return _render_lista(prefixo="✅ Removido da lista.\n\n")
    return Reply("ℹ️ Esse número não estava na lista.")


def _split_titular_espera(entries: list[db.ListaEntry], vagas: int):
    """Mensalistas têm prioridade de titular; o resto entra por ordem de chegada."""
    ordenado = sorted(entries, key=lambda e: (0 if e.player.mensalista else 1, e.ordem))
    return ordenado[:vagas], ordenado[vagas:]


def _render_lista(prefixo: str = "") -> Reply:
    aberta, vagas = db.lista_state()
    entries = db.lista_entries()
    if not entries:
        estado = "aberta" if aberta else "fechada"
        return Reply(f"{prefixo}📝 Lista {estado} — ninguém confirmado ainda. ({vagas} vagas)")

    titulares, espera = _split_titular_espera(entries, vagas)
    cab = "🟢 aberta" if aberta else "🔴 fechada"
    linhas = [f"{prefixo}📝 *LISTA DA PELADA* ({cab}) — {len(titulares)}/{vagas}", ""]
    for i, e in enumerate(titulares, 1):
        tag = "⭐" if e.player.mensalista else ""
        linhas.append(f"{i}. {e.player.name} {tag}".rstrip())
    if espera:
        linhas.append("\n⏳ *Espera:*")
        for i, e in enumerate(espera, 1):
            linhas.append(f"{i}. {e.player.name}")
    return Reply("\n".join(linhas))


def _cmd_lista(_msg: IncomingMessage, _args: list[str]) -> Reply:
    return _render_lista()


# --------------------------------------------------------------- sorteio ----
def _parse_num_times(args: list[str], n: int) -> int:
    for tok in args:
        a = tok.lower()
        if a.startswith("t") and a[1:].isdigit():       # tN = N por time
            por_time = max(1, int(a[1:]))
            return max(1, math.ceil(n / por_time))
        if a.isdigit():                                  # N = N times
            return max(1, int(a))
    return max(2, n // 5)                                # default Fut5


def _cmd_sorteiotimes(_msg: IncomingMessage, args: list[str]) -> Reply:
    _aberta, vagas = db.lista_state()
    titulares, _espera = _split_titular_espera(db.lista_entries(), vagas)
    if len(titulares) < 2:
        return Reply("⚠️ Preciso de pelo menos 2 jogadores na lista pra sortear.")

    num_times = min(_parse_num_times(args, len(titulares)), len(titulares))
    jogadores = [teams.Jogador(e.player.name, e.player.overall) for e in titulares]
    resultado = teams.sortear(jogadores, num_times)

    linhas = ["🎲 *TIMES SORTEADOS*", ""]
    for i, t in enumerate(resultado, 1):
        linhas.append(f"*Time {i}* (força {t.soma} | média {t.media:.1f})")
        for j in t.jogadores:
            linhas.append(f"  • {j.name} ({j.overall})")
        linhas.append("")
    return Reply("\n".join(linhas).rstrip())


# ----------------------------------------------------------------- ajuda ----
def _cmd_ajuda(_msg: IncomingMessage, _args: list[str]) -> Reply:
    return Reply(
        "⚽ *Bot da Pelada*\n\n"
        "*Cadastro (admin):*\n"
        "• .cadastro <número> <nota> <nome>\n"
        "• .remover <número>\n"
        "• .mensalista <número> / .diarista <número>\n"
        "• .jogadores\n\n"
        "*Lista da pelada:*\n"
        "• .abrirlista [vagas] / .fecharlista (admin)\n"
        "• .vou / .naovou (qualquer jogador)\n"
        "• .vai <número> <nota> <nome> (admin: cadastra e bota na lista)\n"
        "• .tira <número> (admin)\n"
        "• .lista\n\n"
        "*Sorteio:*\n"
        "• .sorteiotimes [n]  (n times, ou tN p/ N por time)"
    )


_HANDLERS = {
    "cadastro": _cmd_cadastro,
    "remover": _cmd_remover,
    "mensalista": lambda m, a: _cmd_mensalista(m, a, True),
    "diarista": lambda m, a: _cmd_mensalista(m, a, False),
    "jogadores": _cmd_jogadores,
    "abrirlista": _cmd_abrirlista,
    "fecharlista": _cmd_fecharlista,
    "vou": _cmd_vou,
    "naovou": _cmd_naovou,
    "vai": _cmd_vai,
    "tira": _cmd_tira,
    "lista": _cmd_lista,
    "sorteiotimes": _cmd_sorteiotimes,
    "sortear": _cmd_sorteiotimes,
    "ajuda": _cmd_ajuda,
    "help": _cmd_ajuda,
}


def handle(msg: IncomingMessage) -> Reply | None:
    if not msg.text.startswith(PREFIX):
        return None
    parts = msg.text[len(PREFIX):].split()
    if not parts:
        return None
    handler = _HANDLERS.get(parts[0].lower())
    return handler(msg, parts[1:]) if handler else None
