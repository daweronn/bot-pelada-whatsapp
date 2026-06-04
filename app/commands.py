"""Interpretação e execução dos comandos do bot."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import db, teams
from .config import settings
from .messages import IncomingMessage
from .phones import canonical_phone, only_digits

PREFIX = "."
LINHA = "━━━━━━━━━━━━━━━"
TIME_EMOJIS = ["🟦", "🟥", "🟩", "🟨", "🟪", "🟧", "⬛", "⬜"]


@dataclass
class Reply:
    text: str
    mentions: list[str] = field(default_factory=list)


# ------------------------------------------------------------- utilidades ----
def _is_admin(msg: IncomingMessage) -> bool:
    return msg.from_me or settings.is_admin(msg.sender_phone)


def _so_admin(acao: str) -> Reply:
    return Reply(f"🚫 *Apenas o admin* pode {acao}.")


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
_EX_CAD = "_Exemplo:_ `.cadastro 5522998720569 7 João Marcelo`"


def _cmd_cadastro(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("cadastrar jogadores")

    phone, rest = _extract_phone(args)
    if not phone:
        return Reply(f"❓ Faltou o *número* (com DDD).\n{_EX_CAD}")
    overall, rest = _extract_overall(rest)
    if overall is None:
        return Reply(f"❓ Faltou a *nota* (de 1 a 10).\n{_EX_CAD}")
    name = _join_name(rest)
    if not name:
        existing = db.get_player(phone)
        if existing:
            name = existing.name  # atualização só da nota mantém o nome
        else:
            return Reply(f"❓ Faltou o *nome* do jogador.\n{_EX_CAD}")

    is_new = db.upsert_player(phone, name, overall)
    titulo = "Jogador cadastrado" if is_new else "Cadastro atualizado"
    return Reply(f"✅ *{titulo}!*\n👤 {name}\n🎯 Overall: *{overall}/10*")


def _cmd_remover(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("remover jogadores")
    phone, _ = _extract_phone(args)
    if not phone:
        return Reply("❓ Informe o número.\n_Exemplo:_ `.remover 5522998720569`")
    if db.remove_player(phone):
        return Reply("🗑️ *Jogador removido.*")
    return Reply("ℹ️ Esse número não estava cadastrado.")


def _cmd_mensalista(msg: IncomingMessage, args: list[str], value: bool) -> Reply:
    if not _is_admin(msg):
        return _so_admin("alterar mensalistas")
    phone, _ = _extract_phone(args)
    if not phone:
        return Reply("❓ Informe o número.\n_Exemplo:_ `.mensalista 5522998720569`")
    if not db.set_mensalista(phone, value):
        return Reply("❓ Número não cadastrado. Cadastre antes com `.cadastro`.")
    if value:
        return Reply("⭐ Agora é *mensalista* (vaga prioritária).")
    return Reply("✅ Agora é *diarista* (avulso).")


def _cmd_jogadores(_msg: IncomingMessage, _args: list[str]) -> Reply:
    players = db.list_players()
    if not players:
        return Reply("📋 Nenhum jogador cadastrado ainda.\nUse `.cadastro` pra começar.")
    linhas = [f"📋 *JOGADORES CADASTRADOS* ({len(players)})", LINHA]
    for p in players:
        tag = "⭐" if p.mensalista else "▫️"
        linhas.append(f"{tag} {p.name} — *{p.overall}*")
    linhas += [LINHA, "_⭐ mensalista  ▫️ diarista_"]
    return Reply("\n".join(linhas))


# ------------------------------------------------------------------ lista ----
def _cmd_abrirlista(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("abrir a lista")
    vagas = 10
    for tok in args:
        if tok.isdigit():
            vagas = int(tok)
            break
    db.open_lista(vagas)
    return Reply(
        f"🟢 *LISTA ABERTA!*\n👥 {vagas} vagas\n{LINHA}\n"
        "✅ Mande *.vou* pra confirmar sua presença\n"
        "📋 Acompanhe com *.lista*"
    )


def _cmd_fecharlista(msg: IncomingMessage, _args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("fechar a lista")
    db.close_lista()
    return Reply("🔴 *LISTA FECHADA!*\n🎲 Monte os times com *.sorteiotimes*")


def _cmd_vou(msg: IncomingMessage, _args: list[str]) -> Reply:
    aberta, _ = db.lista_state()
    if not aberta:
        return Reply("⚠️ Não tem lista aberta agora.\nPeça pro admin abrir com `.abrirlista`.")
    phone = canonical_phone(msg.sender_phone)
    player = db.get_player(phone)
    novo = player is None
    if novo:
        # diarista sem cadastro: entra com nota média e o nome do WhatsApp
        nome = msg.sender_name.strip() or "Diarista"
        db.upsert_player(phone, nome, settings.default_overall, mensalista=False)
    if not db.add_to_lista(phone):
        return Reply("✅ Você *já está* na lista! 👍")
    extra = f"\n_(diarista, nota {settings.default_overall} — admin pode ajustar)_" if novo else ""
    return _render_lista(prefixo=f"✅ *Presença confirmada!*{extra}\n\n")


def _cmd_naovou(msg: IncomingMessage, _args: list[str]) -> Reply:
    phone = canonical_phone(msg.sender_phone)
    if db.remove_from_lista(phone):
        return _render_lista(prefixo="👋 *Você saiu da lista.*\n\n")
    return Reply("ℹ️ Você não estava na lista.")


def _cmd_vai(msg: IncomingMessage, args: list[str]) -> Reply:
    """Admin: cadastra (ou atualiza) e já coloca na lista."""
    if not _is_admin(msg):
        return _so_admin("usar o `.vai`")
    aberta, _ = db.lista_state()
    if not aberta:
        return Reply("⚠️ Abra a lista antes com *.abrirlista*.")
    phone, rest = _extract_phone(args)
    if not phone:
        return Reply("❓ Informe o número.\n_Exemplo:_ `.vai 5522998720569 7 João`")
    overall, rest = _extract_overall(rest)
    name = _join_name(rest)
    existing = db.get_player(phone)
    if overall is None:
        overall = existing.overall if existing else settings.default_overall
    if not name:
        name = existing.name if existing else "Diarista"
    db.upsert_player(phone, name, overall)
    db.add_to_lista(phone)
    return _render_lista(prefixo=f"✅ *{name}* entrou na lista! _(overall {overall})_\n\n")


def _cmd_tira(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("tirar da lista")
    phone, _ = _extract_phone(args)
    if not phone:
        return Reply("❓ Informe o número.\n_Exemplo:_ `.tira 5522998720569`")
    if db.remove_from_lista(phone):
        return _render_lista(prefixo="🗑️ *Removido da lista.*\n\n")
    return Reply("ℹ️ Esse número não estava na lista.")


def _split_titular_espera(entries: list[db.ListaEntry], vagas: int):
    """Mensalistas têm prioridade de titular; o resto entra por ordem de chegada."""
    ordenado = sorted(entries, key=lambda e: (0 if e.player.mensalista else 1, e.ordem))
    return ordenado[:vagas], ordenado[vagas:]


def _render_lista(prefixo: str = "") -> Reply:
    aberta, vagas = db.lista_state()
    entries = db.lista_entries()
    cab = "🟢 ABERTA" if aberta else "🔴 FECHADA"
    if not entries:
        return Reply(
            f"{prefixo}📝 *LISTA DA PELADA* ({cab})\n{LINHA}\n"
            f"Ninguém confirmado ainda. ({vagas} vagas)"
        )

    titulares, espera = _split_titular_espera(entries, vagas)
    linhas = [
        f"{prefixo}📝 *LISTA DA PELADA* ({cab})",
        f"👥 Titulares: {len(titulares)}/{vagas}",
        LINHA,
    ]
    for i, e in enumerate(titulares, 1):
        tag = " ⭐" if e.player.mensalista else ""
        linhas.append(f"{i}. {e.player.name}{tag}")
    if espera:
        linhas += [LINHA, "⏳ *Lista de espera:*"]
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
        return Reply("⚠️ Preciso de pelo menos *2 jogadores* na lista pra sortear.")

    num_times = min(_parse_num_times(args, len(titulares)), len(titulares))
    jogadores = [teams.Jogador(e.player.name, e.player.overall) for e in titulares]
    resultado = teams.sortear(jogadores, num_times)

    linhas = ["🎲 *TIMES SORTEADOS* 🎲", LINHA]
    for i, t in enumerate(resultado, 1):
        emoji = TIME_EMOJIS[(i - 1) % len(TIME_EMOJIS)]
        linhas.append(f"{emoji} *Time {i}*  ·  força {t.soma} · média {t.media:.1f}")
        for j in t.jogadores:
            linhas.append(f"   • {j.name} _({j.overall})_")
        linhas.append("")
    linhas.append(LINHA)
    linhas.append("⚖️ _Times equilibrados pela soma dos overalls._")
    return Reply("\n".join(linhas))


# ----------------------------------------------------------------- ajuda ----
def _cmd_ajuda(_msg: IncomingMessage, _args: list[str]) -> Reply:
    return Reply(
        "⚽ *BOT DA PELADA* ⚽\n"
        "_Cadastro, lista de presença e sorteio de times._\n"
        f"{LINHA}\n"
        "👤 *JOGADORES* _(admin)_\n"
        "• *.cadastro* _número nota nome_\n"
        "   ↳ cadastra/atualiza um jogador\n"
        "   ↳ _ex.: .cadastro 5522998720569 7 João_\n"
        "• *.remover* _número_\n"
        "• *.mensalista* _número_  ↳ vira fixo ⭐\n"
        "• *.diarista* _número_  ↳ vira avulso\n"
        "• *.jogadores*  ↳ lista todos os cadastrados\n"
        f"{LINHA}\n"
        "📝 *LISTA DA PELADA*\n"
        "• *.abrirlista* _[vagas]_  ↳ abre _(admin, padrão 10)_\n"
        "• *.vou*  ↳ confirmo minha presença ✅\n"
        "• *.naovou*  ↳ saio da lista\n"
        "• *.vai* _número nota nome_  ↳ _(admin)_ cadastra e já põe na lista\n"
        "• *.tira* _número_  ↳ _(admin)_ remove da lista\n"
        "• *.lista*  ↳ mostra titulares + espera\n"
        "• *.fecharlista*  ↳ fecha _(admin)_\n"
        f"{LINHA}\n"
        "🎲 *SORTEIO*\n"
        "• *.sorteiotimes*  ↳ times equilibrados _(Fut5, 5/time)_\n"
        "• *.sorteiotimes 4*  ↳ força 4 times\n"
        "• *.sorteiotimes t6*  ↳ 6 jogadores por time\n"
        f"{LINHA}\n"
        "💡 *Dicas:*\n"
        "▫️ Mensalistas ⭐ têm prioridade de vaga sobre diaristas.\n"
        "▫️ Quem manda *.vou* sem cadastro entra como diarista com nota 5.\n"
        f"▫️ Pode cadastrar o número com ou sem o 9 — o bot ajusta sozinho."
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
