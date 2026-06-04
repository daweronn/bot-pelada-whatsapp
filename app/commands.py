"""Interpretação e execução dos comandos do bot."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import db, teams
from .config import settings
from .messages import IncomingMessage, jid_to_phone
from .phones import canonical_phone, only_digits

PREFIX = "."
LINHA = "━━━━━━━━━━━━━━━"
TIME_EMOJIS = ["🟦", "🟥", "🟩", "🟨", "🟪", "🟧", "⬛", "⬜"]
MENSALISTA = "⭐"
DIARISTA = "🔹"
DINHEIRO = "💰"


@dataclass
class Reply:
    text: str
    mentions: list[str] = field(default_factory=list)


# ------------------------------------------------------------- utilidades ----
def _is_admin(msg: IncomingMessage) -> bool:
    if msg.from_me:
        return True
    candidatos = msg.phone_candidates or [msg.sender_phone]
    return settings.is_admin_any(candidatos)


def _so_admin(acao: str) -> Reply:
    return Reply(f"🚫 *Apenas o admin* pode {acao}.")


def _extract_phone(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Acha o 1º token que pareça telefone (>=10 dígitos) e o canoniza."""
    for i, tok in enumerate(tokens):
        if len(only_digits(tok)) >= 10:
            rest = tokens[:i] + tokens[i + 1 :]
            return canonical_phone(tok), rest
    return None, tokens


def _mention_identity(msg: IncomingMessage, tokens: list[str]) -> tuple[str | None, list[str]]:
    """Se houver menção (@), devolve a identidade (LID/canônica) e remove os tokens @."""
    if msg.mentioned_jids:
        ident = canonical_phone(jid_to_phone(msg.mentioned_jids[0]))
        rest = [t for t in tokens if not t.startswith("@")]
        return ident, rest
    return None, tokens


def _resolve_alvo(msg: IncomingMessage, args: list[str]) -> tuple[str | None, Reply | None]:
    """Resolve um jogador existente por MENÇÃO, NÚMERO ou NOME.
    Retorna (identidade, None) em sucesso, ou (None, Reply_de_erro)."""
    ident, _ = _mention_identity(msg, args)
    if ident:
        return ident, None
    phone, _ = _extract_phone(args)
    if phone:
        return phone, None
    nome = _join_name(args)
    if not nome:
        return None, Reply("❓ Informe o *número* ou o *nome* do jogador.")
    matches = db.find_players_by_name(nome)
    if not matches:
        return None, Reply(f"❓ Não achei ninguém chamado *{nome}*. Confira o nome ou use o número.")
    if len(matches) > 1:
        nomes = ", ".join(p.name for p in matches[:6])
        return None, Reply(f"⚠️ Mais de um jogador parecido: {nomes}.\nUse o *número* pra não ter dúvida.")
    return matches[0].phone, None


def _extract_overall(tokens: list[str]) -> tuple[int | None, list[str]]:
    for i, tok in enumerate(tokens):
        if tok.isdigit() and 1 <= int(tok) <= 10:
            return int(tok), tokens[:i] + tokens[i + 1 :]
    return None, tokens


def _join_name(tokens: list[str]) -> str:
    return " ".join(t for t in tokens if t != "-").strip()


# --------------------------------------------------------------- cadastro ----
_EX_CAD = (
    "_Use uma destas formas:_\n"
    "• `.cadastro @Fulano 7 Fulano` _(marca a pessoa — recomendado p/ .vou funcionar)_\n"
    "• `.cadastro 5522998720569 7 Fulano` _(por número)_\n"
    "• `.cadastro Fulano 8` _(ajusta a nota de quem já apareceu)_"
)


def _cmd_cadastro(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("cadastrar jogadores")

    # identidade: menção (@) tem prioridade (mesmo ID do .vou); senão número
    ident, rest = _mention_identity(msg, args)
    if not ident:
        ident, rest = _extract_phone(rest)

    if ident:
        overall, rest = _extract_overall(rest)
        if overall is None:
            return Reply(f"❓ Faltou a *nota* (de 1 a 10).\n{_EX_CAD}")
        name = _join_name(rest)
        if not name:
            existing = db.get_player(ident)
            if existing:
                name = existing.name  # atualização só da nota mantém o nome
            else:
                return Reply(f"❓ Faltou o *nome* do jogador.\n{_EX_CAD}")
        is_new = db.upsert_player(ident, name, overall)
        titulo = "Jogador cadastrado" if is_new else "Cadastro atualizado"
        return Reply(f"✅ *{titulo}!*\n👤 {name}\n🎯 Overall: *{overall}/10*")

    # sem menção e sem número → ajusta a NOTA de um jogador já existente, por nome
    overall, rest = _extract_overall(rest)
    nome = _join_name(rest)
    if not nome:
        return Reply(f"❓ Não entendi o jogador.\n{_EX_CAD}")
    if overall is None:
        return Reply(f"❓ Pra ajustar pelo nome, informe a nota. Ex.: `.cadastro {nome} 8`")
    matches = db.find_players_by_name(nome)
    if not matches:
        return Reply(
            f"❓ Não achei *{nome}* cadastrado.\n"
            "Peça pra pessoa mandar *.vou* (aí ela aparece), ou cadastre com *@menção* / número."
        )
    if len(matches) > 1:
        nomes = ", ".join(p.name for p in matches[:6])
        return Reply(f"⚠️ Mais de um parecido: {nomes}. Use *@menção* ou número.")
    alvo = matches[0]
    db.upsert_player(alvo.phone, alvo.name, overall)
    return Reply(f"✅ *Cadastro atualizado!*\n👤 {alvo.name}\n🎯 Overall: *{overall}/10*")


def _cmd_remover(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("remover jogadores")
    phone, erro = _resolve_alvo(msg, args)
    if erro:
        return erro
    if db.remove_player(phone):
        return Reply("🗑️ *Jogador removido.*")
    return Reply("ℹ️ Esse jogador não estava cadastrado.")


def _placeholder_name(ident: str) -> str:
    return f"Jogador {ident[-5:]}"


def _is_placeholder(name: str) -> bool:
    return name.startswith("Jogador ")


def _cmd_mensalista(msg: IncomingMessage, args: list[str], value: bool) -> Reply:
    if not _is_admin(msg):
        return _so_admin("alterar mensalistas")

    tipo = "mensalista" if value else "diarista"
    emo = MENSALISTA if value else DIARISTA

    # ---- EM MASSA por menções: .mensalista @David @Daniel @Marcelinho ----
    if msg.mentioned_jids:
        feitos: list[str] = []
        for jid in msg.mentioned_jids:
            ident = canonical_phone(jid_to_phone(jid))
            if not ident:
                continue
            p = db.get_player(ident)
            if p:
                db.set_mensalista(ident, value)
                feitos.append(p.name)
            elif value:
                # ainda não cadastrado: cria já como mensalista (nome ajusta no .vou)
                nome = _placeholder_name(ident)
                db.upsert_player(ident, nome, settings.default_overall, mensalista=True)
                feitos.append(nome)
        if not feitos:
            return Reply("❓ Não consegui marcar ninguém. Tente mencionar de novo.")
        linhas = [f"{emo} *{len(feitos)} marcado(s) como {tipo}:*"]
        linhas += [f"{emo} {n}" for n in feitos]
        if value and any(_is_placeholder(n) for n in feitos):
            linhas.append("\n_O nome se ajusta sozinho quando a pessoa mandar *.vou*._")
        return Reply("\n".join(linhas))

    # ---- individual por número/nome ----
    phone, erro = _resolve_alvo(msg, args)
    if erro:
        return erro
    if not db.set_mensalista(phone, value):
        return Reply("❓ Esse jogador não está cadastrado. Cadastre antes com `.cadastro`.")
    p = db.get_player(phone)
    nome = p.name if p else ""
    if value:
        return Reply(f"{MENSALISTA} *{nome}* agora é *mensalista* — vaga garantida em toda lista.")
    return Reply(f"{DIARISTA} *{nome}* agora é *diarista* (avulso).")


def _cmd_pagou(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("marcar pagamentos")

    # ---- EM MASSA por menções: .pagou @David @Daniel @Marcelinho ----
    if msg.mentioned_jids:
        feitos: list[str] = []
        for jid in msg.mentioned_jids:
            ident = canonical_phone(jid_to_phone(jid))
            if not ident:
                continue
            p = db.get_player(ident)
            if not p:
                # não cadastrado: cria como mensalista (quem paga é mensalista)
                nome = _placeholder_name(ident)
                db.upsert_player(ident, nome, settings.default_overall, mensalista=True)
                p = db.get_player(ident)
            db.set_pagou(ident, True)
            feitos.append(p.name)
        if not feitos:
            return Reply("❓ Não consegui marcar ninguém. Tente mencionar de novo.")
        linhas = [f"{DINHEIRO} *{len(feitos)} marcado(s) como PAGO:*"]
        linhas += [f"{DINHEIRO} {n}" for n in feitos]
        return Reply("\n".join(linhas))

    # ---- individual por número/nome ----
    phone, erro = _resolve_alvo(msg, args)
    if erro:
        return erro
    if not db.set_pagou(phone, True):
        return Reply("❓ Esse jogador não está cadastrado.")
    p = db.get_player(phone)
    return Reply(f"{DINHEIRO} *{p.name}* marcado como *pago*.")


def _cmd_resetpagamento(msg: IncomingMessage, _args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("resetar pagamentos")
    n = db.reset_pagamentos()
    return Reply(
        f"🧹 *Pagamentos zerados!*\n{n} estavam como pagos — agora todos estão *não pagos*."
    )


def _cmd_jogadores(_msg: IncomingMessage, _args: list[str]) -> Reply:
    players = db.list_players()
    if not players:
        return Reply("📋 Nenhum jogador cadastrado ainda.\nUse `.cadastro` pra começar.")
    linhas = [f"📋 *JOGADORES CADASTRADOS* ({len(players)})", LINHA]
    for p in players:
        tag = MENSALISTA if p.mensalista else DIARISTA
        pago = f" {DINHEIRO}" if p.pagou else ""
        linhas.append(f"{tag} {p.name}{pago} — *{p.overall}*")
    linhas += [LINHA, f"_{MENSALISTA} mensalista   {DIARISTA} diarista   {DINHEIRO} pagou_"]
    return Reply("\n".join(linhas))


# ------------------------------------------------------------------ lista ----
def _cmd_abrirlista(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("abrir a lista")
    vagas = 15
    for tok in args:
        if tok.isdigit():
            vagas = int(tok)
            break
    n_mensalistas = db.open_lista(vagas)
    nota = (
        f"⭐ {n_mensalistas} mensalista(s) já entraram automaticamente.\n"
        if n_mensalistas
        else ""
    )
    prefixo = (
        f"🟢 *LISTA ABERTA!* — {vagas} vagas\n"
        f"{nota}"
        "✅ Diaristas: mandem *.vou* pra confirmar.\n"
        "❌ Mensalista que não vai: mande *.naovou*.\n\n"
    )
    return _render_lista(prefixo=prefixo)


def _cmd_fecharlista(msg: IncomingMessage, _args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("fechar a lista")
    db.close_lista()
    return Reply("🔴 *LISTA FECHADA!*\n🎲 Monte os times com *.sorteiotimes*")


def _identities(msg: IncomingMessage) -> list[str]:
    """Todos os identificadores que o remetente carrega (telefone real + LID)."""
    ids = list(msg.phone_candidates)
    lid = canonical_phone(jid_to_phone(msg.sender_jid))
    if lid and lid not in ids:
        ids.append(lid)
    if not ids:
        ids = [canonical_phone(msg.sender_phone)]
    return [i for i in ids if i]


def _find_existing(ids: list[str]) -> tuple[db.Player | None, str]:
    """Procura um jogador já cadastrado por qualquer identidade. Retorna (player, chave)."""
    for c in ids:
        p = db.get_player(c)
        if p:
            return p, c
    return None, ids[0]


def _cmd_vou(msg: IncomingMessage, _args: list[str]) -> Reply:
    aberta, _ = db.lista_state()
    if not aberta:
        return Reply("⚠️ Não tem lista aberta agora.\nPeça pro admin abrir com `.abrirlista`.")

    ids = _identities(msg)
    player, key = _find_existing(ids)
    novo = player is None
    pn = msg.sender_name.strip()
    if novo:
        # diarista sem cadastro: entra com nota média e o nome do WhatsApp
        db.upsert_player(key, pn or "Diarista", settings.default_overall, mensalista=False)
    elif pn and _is_placeholder(player.name):
        # já existia só com placeholder -> agora aprendemos o nome real
        db.upsert_player(key, pn, player.overall, player.mensalista)

    if not db.add_to_lista(key):
        return Reply("✅ Você *já está* na lista! 👍")
    extra = f"\n_(diarista, nota {settings.default_overall} — admin pode ajustar)_" if novo else ""
    return _render_lista(prefixo=f"✅ *Presença confirmada!*{extra}\n\n")


def _cmd_naovou(msg: IncomingMessage, _args: list[str]) -> Reply:
    removido = False
    for c in _identities(msg):
        if db.remove_from_lista(c):
            removido = True
    if removido:
        return _render_lista(prefixo="👋 *Você saiu da lista.* O próximo da espera subiu. ⬆️\n\n")
    return Reply("ℹ️ Você não estava na lista.")


def _cmd_vai(msg: IncomingMessage, args: list[str]) -> Reply:
    """Admin: cadastra (ou atualiza) e já coloca na lista."""
    if not _is_admin(msg):
        return _so_admin("usar o `.vai`")
    aberta, _ = db.lista_state()
    if not aberta:
        return Reply("⚠️ Abra a lista antes com *.abrirlista*.")
    # menção (@) tem prioridade; senão número; senão nome de quem já existe
    ident, rest = _mention_identity(msg, args)
    if not ident:
        ident, rest = _extract_phone(rest)
    overall, rest = _extract_overall(rest)
    name = _join_name(rest)
    if not ident:
        if not name:
            return Reply("❓ Use `.vai @Fulano 7 Nome`, `.vai 5522998720569 7 Nome` ou `.vai Nome`.")
        matches = db.find_players_by_name(name)
        if len(matches) != 1:
            return Reply("❓ Não achei esse jogador. Use *@menção* ou número.")
        ident = matches[0].phone
        name = ""
    existing = db.get_player(ident)
    if overall is None:
        overall = existing.overall if existing else settings.default_overall
    if not name:
        name = existing.name if existing else "Diarista"
    db.upsert_player(ident, name, overall)
    db.add_to_lista(ident)
    return _render_lista(prefixo=f"✅ *{name}* entrou na lista! _(overall {overall})_\n\n")


def _cmd_tira(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _is_admin(msg):
        return _so_admin("tirar da lista")
    phone, erro = _resolve_alvo(msg, args)
    if erro:
        return erro
    if db.remove_from_lista(phone):
        return _render_lista(prefixo="🗑️ *Saiu da lista.* O próximo da espera subiu. ⬆️\n\n")
    return Reply("ℹ️ Esse jogador não estava na lista.")


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
        tag = MENSALISTA if e.player.mensalista else DIARISTA
        pago = f" {DINHEIRO}" if e.player.pagou else ""
        linhas.append(f"{i}. {tag} {e.player.name}{pago}")
    if espera:
        linhas += [LINHA, f"⏳ *Lista de espera* ({len(espera)}):"]
        for i, e in enumerate(espera, 1):
            tag = MENSALISTA if e.player.mensalista else DIARISTA
            pago = f" {DINHEIRO}" if e.player.pagou else ""
            linhas.append(f"{i}. {tag} {e.player.name}{pago}")
    linhas += [LINHA, f"_{MENSALISTA} mensalista   {DIARISTA} diarista   {DINHEIRO} pagou_"]
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
        "• *.cadastro* _@pessoa nota nome_  ↳ recomendado 👈\n"
        "   ↳ marcar com @ liga o cadastro ao *.vou* da pessoa\n"
        "   ↳ _ex.: .cadastro @João 7 João_\n"
        "   ↳ também: `.cadastro 5522998720569 7 João` ou `.cadastro João 8`\n"
        "• *.remover* _@pessoa/número/nome_\n"
        f"• *.mensalista* _@um @dois @três_  ↳ marca vários de uma vez {MENSALISTA}\n"
        f"• *.diarista* _@pessoa/número/nome_  ↳ vira avulso {DIARISTA}\n"
        "• *.jogadores*  ↳ lista todos os cadastrados\n"
        f"{LINHA}\n"
        f"{DINHEIRO} *PAGAMENTO* _(admin)_\n"
        "• *.pagou* _@um @dois @três_  ↳ marca quem pagou\n"
        "• *.resetpagamento*  ↳ zera todos (início do mês)\n"
        f"{LINHA}\n"
        "📝 *LISTA DA PELADA* _(padrão 15 vagas = 3 times de 5)_\n"
        "• *.abrirlista* _[vagas]_  ↳ abre e já inclui os mensalistas _(admin)_\n"
        "• *.vou*  ↳ confirmo minha presença ✅\n"
        "• *.naovou*  ↳ saio da lista\n"
        "• *.vai* _número nota nome_  ↳ _(admin)_ cadastra e já põe na lista\n"
        "• *.tira* _número/nome_  ↳ _(admin)_ tira alguém da lista\n"
        "• *.lista*  ↳ mostra titulares + espera\n"
        "• *.fecharlista*  ↳ fecha _(admin)_\n"
        f"{LINHA}\n"
        "🎲 *SORTEIO*\n"
        "• *.sorteiotimes*  ↳ times equilibrados _(Fut5, 5/time)_\n"
        "• *.sorteiotimes 4*  ↳ força 4 times\n"
        "• *.sorteiotimes t6*  ↳ 6 jogadores por time\n"
        f"{LINHA}\n"
        "💡 *Como funciona a vaga:*\n"
        f"{MENSALISTA} Mensalista entra automático na lista; só sai se mandar *.naovou*.\n"
        f"{DIARISTA} Diarista manda *.vou*; sem cadastro, entra com nota 5.\n"
        "⬆️ Se um titular sai, o 1º da espera sobe sozinho.\n"
        "🔢 Número pode ser com ou sem o 9 — o bot ajusta sozinho."
    )


_HANDLERS = {
    "cadastro": _cmd_cadastro,
    "remover": _cmd_remover,
    "mensalista": lambda m, a: _cmd_mensalista(m, a, True),
    "diarista": lambda m, a: _cmd_mensalista(m, a, False),
    "pagou": _cmd_pagou,
    "resetpagamento": _cmd_resetpagamento,
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
