"""Testes locais da lógica, sem Evolution API.  Roda: python -m tests.test_commands"""
import os
import tempfile

os.environ["ADMIN_NUMBERS"] = "5522998720569"   # com o 9
os.environ["DEFAULT_OVERALL"] = "5"
os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "pelada_test.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

from app import commands, db          # noqa: E402
from app.messages import parse_event  # noqa: E402
from app.phones import canonical_phone  # noqa: E402

GROUP = "12036304@g.us"
# João Marcelo enviando: o WhatsApp manda SEM o 9 (552298720569)
ADMIN_SEM9 = "552298720569@s.whatsapp.net"
PLAYER = "5511555550000@s.whatsapp.net"


def evt(sender_jid, text, from_me=False, push="Tester"):
    return {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": GROUP, "participant": sender_jid, "fromMe": from_me},
            "pushName": push,
            "message": {"conversation": text},
        },
    }


def run(sender_jid, text, **kw):
    msg = parse_event(evt(sender_jid, text, **kw))
    assert msg is not None, f"não parseou: {text}"
    return commands.handle(msg)


def main() -> None:
    db.init_db()

    # ---- normalização do 9º dígito ----
    assert canonical_phone("5522998720569") == canonical_phone("552298720569")
    assert canonical_phone("22998720569") == canonical_phone("5522998720569")

    # ---- ADMIN reconhecido mesmo o número chegando SEM o 9 (bug do João) ----
    r = run(ADMIN_SEM9, ".cadastro 5511111111111 8 Alfa")
    assert "Alfa" in r.text and "🚫" not in r.text, r.text

    # ---- cadastro: todos os campos obrigatórios ----
    assert "número" in run(ADMIN_SEM9, ".cadastro 7 SemNumero").text.lower()
    assert "nota" in run(ADMIN_SEM9, ".cadastro 5511222222222 SemNota").text.lower()
    assert "nome" in run(ADMIN_SEM9, ".cadastro 5511333333333 6").text.lower()

    # cadastra mais dois
    run(ADMIN_SEM9, ".cadastro 5511222222222 6 Bravo")
    run(ADMIN_SEM9, ".cadastro 5511333333333 4 Charlie")

    # não-admin barrado
    assert "🚫" in run(PLAYER, ".cadastro 5511444444444 9 X").text

    # ---- mensalista ----
    assert "mensalista" in run(ADMIN_SEM9, ".mensalista 5511333333333").text.lower()

    # ---- lista ----
    assert "aberta" in run(ADMIN_SEM9, ".abrirlista 2").text.lower()
    run(ADMIN_SEM9, ".vai 5511111111111")   # Alfa
    run(ADMIN_SEM9, ".vai 5511222222222")   # Bravo
    run(ADMIN_SEM9, ".vai 5511333333333")   # Charlie (mensalista, chegou por último)

    r = run(PLAYER, ".lista")
    # com 2 vagas, o mensalista Charlie deve ser TITULAR; Bravo vai pra espera
    assert "Charlie" in r.text and "espera" in r.text.lower(), r.text
    pos_titular = r.text.lower().index("charlie")
    pos_espera = r.text.lower().index("espera")
    assert pos_titular < pos_espera, r.text  # Charlie está antes da seção de espera

    # ---- .vou cria diarista com nota média + nome do WhatsApp ----
    r = run(PLAYER, ".vou", push="Diego")
    assert "confirmada" in r.text.lower(), r.text
    p = db.get_player(canonical_phone("5511555550000"))
    assert p is not None and p.name == "Diego" and p.overall == 5, p

    # já está na lista -> idempotente
    assert "já está" in run(PLAYER, ".vou", push="Diego").text.lower()

    # ---- sorteio ----
    r = run(ADMIN_SEM9, ".sorteiotimes 2")
    assert "TIMES SORTEADOS" in r.text and "Time 1" in r.text and "Time 2" in r.text, r.text

    print("OK - todos os testes passaram ✅\n")
    print(run(ADMIN_SEM9, ".sorteiotimes 2").text)


if __name__ == "__main__":
    main()
