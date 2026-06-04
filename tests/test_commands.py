"""Teste local da lógica de comandos, sem Evolution API.

Roda com:  python -m tests.test_commands
"""
import os
import tempfile

# configura ambiente ANTES de importar o app
os.environ["ADMIN_NUMBERS"] = "5511999999999"
os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "pelada_test.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

from app import commands, db  # noqa: E402
from app.messages import parse_event  # noqa: E402

GROUP = "12036304@g.us"
ADMIN = "5511999999999@s.whatsapp.net"
OUTRO = "5511777777777@s.whatsapp.net"
ALVO = "5511888888888@s.whatsapp.net"


def evt(sender_jid, text, mentioned=None, from_me=False):
    msg = {"extendedTextMessage": {"text": text}} if mentioned else {"conversation": text}
    if mentioned:
        msg["extendedTextMessage"]["contextInfo"] = {"mentionedJid": mentioned}
    return {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": GROUP, "participant": sender_jid, "fromMe": from_me},
            "pushName": "Tester",
            "message": msg,
        },
    }


def run_me(sender_jid, text, mentioned=None):
    msg = parse_event(evt(sender_jid, text, mentioned, from_me=True))
    assert msg is not None
    return commands.handle(msg)


def run(sender_jid, text, mentioned=None):
    msg = parse_event(evt(sender_jid, text, mentioned))
    assert msg is not None, f"não parseou: {text}"
    return commands.handle(msg)


def main() -> None:
    db.init_db()

    # admin cadastra por menção
    r = run(ADMIN, ".cadastro @ZÉ 8 Zé do Gol", mentioned=[ALVO])
    assert "overall *8*" in r.text, r.text
    assert ALVO in r.mentions

    # admin cadastra por número solto, com traço e nome
    r = run(ADMIN, ".cadastro 5511777777777 - 6 Pelé")
    assert "overall *6*" in r.text, r.text

    # nota inválida (11) => não acha nota válida
    r = run(ADMIN, ".cadastro 5511777777777 11 Pelé")
    assert "nota" in r.text.lower(), r.text

    # sem nome em jogador novo => cobra o nome
    r = run(ADMIN, ".cadastro 5511555555555 5")
    assert "nome" in r.text.lower(), r.text

    # não-admin é barrado
    r = run(OUTRO, ".cadastro @ZÉ 9", mentioned=[ALVO])
    assert "admin" in r.text.lower(), r.text

    # a própria instância (fromMe) pode cadastrar, mesmo não estando em ADMIN_NUMBERS
    r = run_me(OUTRO, ".cadastro 5511666666666 - 7 Goleiro")
    assert "overall *7*" in r.text, r.text

    # atualização (mesmo jid) muda overall e diz "atualizado"
    r = run(ADMIN, ".cadastro @ZÉ 10", mentioned=[ALVO])
    assert "atualizado" in r.text and "10" in r.text, r.text

    # listagem ordenada por overall desc
    r = run(OUTRO, ".jogadores")
    assert "Zé do Gol" in r.text and "Pelé" in r.text, r.text
    assert r.text.index("Zé do Gol") < r.text.index("Pelé"), r.text

    # remoção
    r = run(ADMIN, ".remover 5511777777777")
    assert "removido" in r.text.lower(), r.text

    # comando inexistente => None
    msg = parse_event(evt(ADMIN, ".xpto"))
    assert commands.handle(msg) is None

    # mensagem normal (sem prefixo) => None
    msg = parse_event(evt(ADMIN, "bom dia galera"))
    assert commands.handle(msg) is None

    print("OK - todos os testes passaram ✅")
    print("\nJogadores no banco:")
    for p in db.list_players():
        print(f"  {p.name} -> {p.overall}")


if __name__ == "__main__":
    main()
