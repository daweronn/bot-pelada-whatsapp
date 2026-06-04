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
# João enviando: SEM o 9 (552298720569) — e também o cenário LID
ADMIN_SEM9 = "552298720569@s.whatsapp.net"
PLAYER = "5511555550000@s.whatsapp.net"


def evt(text, sender_jid=ADMIN_SEM9, from_me=False, push="Tester", extra_key=None):
    key = {"remoteJid": GROUP, "participant": sender_jid, "fromMe": from_me}
    if extra_key:
        key.update(extra_key)
    return {
        "event": "messages.upsert",
        "data": {"key": key, "pushName": push, "message": {"conversation": text}},
    }


def run(text, **kw):
    msg = parse_event(evt(text, **kw))
    assert msg is not None, f"não parseou: {text}"
    return commands.handle(msg)


def main() -> None:
    db.init_db()

    # ---- normalização do 9º dígito ----
    assert canonical_phone("5522998720569") == canonical_phone("552298720569")
    assert canonical_phone("22998720569") == canonical_phone("5522998720569")

    # ---- ADMIN reconhecido com o número chegando SEM o 9 ----
    r = run(".cadastro 5511111111111 8 Alfa")
    assert "Alfa" in r.text and "🚫" not in r.text, r.text

    # ---- ADMIN via LID + participantPn (o número real vem em outro campo) ----
    msg = parse_event(evt(
        ".jogadores",
        sender_jid="199351024537747@lid",
        extra_key={"participantPn": "5522998720569@s.whatsapp.net"},
    ))
    assert commands._is_admin(msg), "deveria achar o admin pelo participantPn"

    # ---- cadastro: todos os campos obrigatórios ----
    assert "número" in run(".cadastro 7 SemNumero").text.lower()
    assert "nota" in run(".cadastro 5511222222222 SemNota").text.lower()
    assert "nome" in run(".cadastro 5511333333333 6").text.lower()

    run(".cadastro 5511222222222 6 Bravo")
    run(".cadastro 5511333333333 9 Charlie")

    # não-admin barrado
    assert "🚫" in run(".cadastro 5511444444444 9 X", sender_jid=PLAYER).text

    # ---- mensalista POR NOME (admin) ----
    assert "mensalista" in run(".mensalista Charlie").text.lower()
    assert "mensalista" in run(".mensalista Alfa").text.lower()

    # ---- abrirlista já inclui os mensalistas (Alfa, Charlie) ----
    r = run(".abrirlista 3")
    assert "aberta" in r.text.lower() and "Charlie" in r.text and "Alfa" in r.text, r.text

    # diarista entra com .vou
    r = run(".vou", sender_jid=PLAYER, push="Diego")
    assert "confirmada" in r.text.lower(), r.text
    p = db.get_player(canonical_phone("5511555550000"))
    assert p and p.name == "Diego" and p.overall == 5 and not p.mensalista, p

    # admin põe Bravo na lista -> agora são 4 (Alfa, Charlie, Diego, Bravo) em 3 vagas
    run(".vai 5511222222222")
    r = run(".lista")
    assert "espera" in r.text.lower(), r.text  # alguém sobrou pra espera

    # mensalistas são titulares; o último diarista vai pra espera
    titulares, espera = commands._split_titular_espera(db.lista_entries(), 3)
    nomes_tit = {e.player.name for e in titulares}
    assert "Alfa" in nomes_tit and "Charlie" in nomes_tit, nomes_tit

    # ---- promoção: mensalista sai -> diarista da espera sobe ----
    antes_espera = {e.player.name for e in espera}
    run(".naovou", sender_jid=PLAYER, push="Diego")  # tira o Diego (não é quem está na espera)
    # tira um mensalista (Alfa) -> abre vaga de titular
    run(".tira Alfa")
    titulares2, _ = commands._split_titular_espera(db.lista_entries(), 3)
    nomes_tit2 = {e.player.name for e in titulares2}
    # quem estava na espera (Bravo) deve ter virado titular
    assert antes_espera & nomes_tit2, (antes_espera, nomes_tit2)

    # ---- sorteio ----
    r = run(".sorteiotimes 2")
    assert "TIMES SORTEADOS" in r.text and "Time 1" in r.text and "Time 2" in r.text, r.text

    print("OK - todos os testes passaram ✅\n")
    print(run(".lista").text)


if __name__ == "__main__":
    main()
