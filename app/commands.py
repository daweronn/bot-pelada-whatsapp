"""Interpretação e execução dos comandos do bot."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import db
from .config import settings
from .messages import IncomingMessage, jid_to_phone, phone_to_jid

PREFIX = "."


@dataclass
class Reply:
    text: str
    mentions: list[str] = field(default_factory=list)


def _can_register(msg: IncomingMessage) -> bool:
    """Autorizado a cadastrar: o número da própria instância (fromMe)
    ou um número listado em ADMIN_NUMBERS."""
    return msg.from_me or settings.is_admin(msg.sender_phone)


def _resolve_target(msg: IncomingMessage, tokens: list[str]) -> tuple[str | None, list[str]]:
    """Descobre o JID do alvo. Retorna (jid, tokens_restantes_sem_o_alvo)."""
    # 1) menção explícita (@) tem prioridade
    if msg.mentioned_jids:
        jid = msg.mentioned_jids[0]
        # remove o(s) token(s) @... da lista para não virar nome
        rest = [t for t in tokens if not t.startswith("@")]
        return jid, rest

    # 2) número solto no texto (>= 8 dígitos)
    for i, tok in enumerate(tokens):
        digits = re.sub(r"\D", "", tok)
        if len(digits) >= 8:
            rest = tokens[:i] + tokens[i + 1 :]
            return phone_to_jid(digits), rest

    return None, tokens


def _extract_overall(tokens: list[str]) -> tuple[int | None, list[str]]:
    """Acha a nota (1-10) entre os tokens. Retorna (nota, tokens_restantes)."""
    for i, tok in enumerate(tokens):
        if tok.isdigit():
            val = int(tok)
            if 1 <= val <= 10:
                rest = tokens[:i] + tokens[i + 1 :]
                return val, rest
    return None, tokens


_EXEMPLO = "Ex.: *.cadastro @Calebe 5 Calebe*  (ou com número: *.cadastro 5522999334804 5 Calebe*)"


def _cmd_cadastro(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _can_register(msg):
        return Reply("🚫 Só o admin pode cadastrar jogadores.")

    target_jid, rest = _resolve_target(msg, args)
    if not target_jid:
        return Reply("❓ Marque a pessoa (ou informe o número).\n" + _EXEMPLO)

    overall, rest = _extract_overall(rest)
    if overall is None:
        return Reply("❓ Faltou a *nota* (de 1 a 10).\n" + _EXEMPLO)

    # o que sobrou (sem '-') vira o nome — agora o nome é OBRIGATÓRIO
    name = " ".join(t for t in rest if t != "-").strip()
    if not name:
        existing = db.get_player(target_jid)
        if existing and existing.name:
            name = existing.name  # atualização só da nota: mantém o nome
        else:
            return Reply("❓ Faltou o *nome* do jogador.\n" + _EXEMPLO)

    phone = jid_to_phone(target_jid)
    is_new = db.upsert_player(target_jid, phone, name, overall)
    verbo = "cadastrado" if is_new else "atualizado"
    return Reply(
        f"✅ *{name}* {verbo} com overall *{overall}*.",
        mentions=[target_jid],
    )


def _cmd_remover(msg: IncomingMessage, args: list[str]) -> Reply:
    if not _can_register(msg):
        return Reply("🚫 Só o admin pode remover jogadores.")

    target_jid, _ = _resolve_target(msg, args)
    if not target_jid:
        return Reply("❓ Use: *.remover @pessoa* ou *.remover 5511999999999*")

    if db.remove_player(target_jid):
        return Reply("🗑️ Jogador removido.")
    return Reply("ℹ️ Esse jogador não estava cadastrado.")


def _cmd_jogadores(_msg: IncomingMessage, _args: list[str]) -> Reply:
    players = db.list_players()
    if not players:
        return Reply("📋 Nenhum jogador cadastrado ainda.")
    linhas = [f"📋 *Jogadores cadastrados ({len(players)})*", ""]
    for p in players:
        linhas.append(f"• {p.name} — *{p.overall}*")
    return Reply("\n".join(linhas))


def _cmd_ajuda(_msg: IncomingMessage, _args: list[str]) -> Reply:
    return Reply(
        "⚽ *Bot da Pelada*\n\n"
        "*.cadastro* @pessoa nota nome — cadastra/atualiza (só admin)\n"
        "   ex.: .cadastro @Calebe 5 Calebe\n"
        "*.remover* @pessoa — remove jogador (só admin)\n"
        "*.jogadores* — lista os cadastrados\n"
        "*.ajuda* — mostra esta ajuda"
    )


_HANDLERS = {
    "cadastro": _cmd_cadastro,
    "remover": _cmd_remover,
    "jogadores": _cmd_jogadores,
    "lista": _cmd_jogadores,
    "ajuda": _cmd_ajuda,
    "help": _cmd_ajuda,
}


def handle(msg: IncomingMessage) -> Reply | None:
    """Roteia a mensagem para o comando certo. Retorna None se não for comando."""
    if not msg.text.startswith(PREFIX):
        return None

    parts = msg.text[len(PREFIX):].split()
    if not parts:
        return None

    command = parts[0].lower()
    args = parts[1:]

    handler = _HANDLERS.get(command)
    if not handler:
        return None
    return handler(msg, args)
