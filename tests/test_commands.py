"""Testes locais da lógica, sem Evolution API.  Roda: python -m tests.test_commands"""
import os
import tempfile

os.environ["ADMIN_NUMBERS"] = "5522998720569,34810760273925"  # número + LID do admin
os.environ["DEFAULT_OVERALL"] = "5"
os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "pelada_test.db")
if os.path.exists(os.environ["DB_PATH"]):
    os.remove(os.environ["DB_PATH"])

from app import commands, db, teams   # noqa: E402
from app.messages import parse_event  # noqa: E402
from app.phones import canonical_phone  # noqa: E402

GROUP = "12036304@g.us"
ADMIN_LID = "34810760273925@lid"      # admin chega como LID (sem telefone no payload)
DIEGO_LID = "111222333444555@lid"     # diarista/jogador comum, sempre o mesmo LID


def evt(text, sender_jid=ADMIN_LID, from_me=False, push="Tester", mentioned=None):
    msg = {"conversation": text}
    if mentioned:
        msg = {"extendedTextMessage": {"text": text, "contextInfo": {"mentionedJid": mentioned}}}
    return {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": GROUP, "participant": sender_jid, "fromMe": from_me},
            "pushName": push,
            "message": msg,
        },
    }


def run(text, **kw):
    m = parse_event(evt(text, **kw))
    assert m is not None, f"não parseou: {text}"
    return commands.handle(m)


def main() -> None:
    db.init_db()

    # ---- admin reconhecido mesmo chegando como LID (via ADMIN_NUMBERS com o LID) ----
    r = run(".cadastro 5511111111111 8 Alfa")
    assert "Alfa" in r.text and "🚫" not in r.text, r.text

    # ---- .vou / .naovou da MESMA pessoa casam pelo LID (já funciona) ----
    run(".abrirlista 15")
    r = run(".vou", sender_jid=DIEGO_LID, push="Diego")
    assert "confirmada" in r.text.lower(), r.text
    diego = db.get_player(canonical_phone("111222333444555"))
    assert diego and diego.name == "Diego" and diego.overall == 5, diego
    r = run(".naovou", sender_jid=DIEGO_LID, push="Diego")
    assert "saiu" in r.text.lower(), r.text

    # ---- admin ajusta a nota do Diego PELO NOME (ele já apareceu via .vou) ----
    r = run(".cadastro Diego 9")
    assert "atualizado" in r.text.lower() and "9/10" in r.text, r.text
    assert db.get_player(canonical_phone("111222333444555")).overall == 9

    # ---- cadastro por MENÇÃO usa o LID como identidade (liga ao .vou) ----
    # admin menciona o Bravo -> guarda o LID do Bravo
    BRAVO_LID = "999888777666555@lid"
    r = run(".cadastro 7 Bravo", mentioned=[BRAVO_LID])
    assert "Bravo" in r.text, r.text
    # quando o Bravo manda .vou (mesmo LID), o bot reconhece: NÃO duplica, mantém nota 7
    run(".vou", sender_jid=BRAVO_LID, push="Bravo")
    bravo = db.get_player(canonical_phone("999888777666555"))
    assert bravo and bravo.overall == 7, bravo  # 7 (do cadastro), não 5

    # ---- .mensalista EM MASSA por menções (cria/marca pelos LIDs) ----
    DAVID_LID = "100000000000001@lid"
    DANIEL_LID = "100000000000002@lid"
    r = run(".mensalista lixo", mentioned=[DAVID_LID, DANIEL_LID, DIEGO_LID])
    assert "3 marcado" in r.text.lower(), r.text
    assert db.get_player(canonical_phone("100000000000001")).mensalista
    assert db.get_player(canonical_phone("111222333444555")).mensalista  # Diego

    # mensalista recém-criado (David) manda .vou -> NÃO duplica, e aprende o nome
    run(".abrirlista 15")
    run(".vou", sender_jid=DAVID_LID, push="David")
    davids = [p for p in db.list_players() if p.name == "David"]
    assert len(davids) == 1 and davids[0].mensalista, davids  # 1 só, e mensalista

    # ---- mensalista se tira pelo próprio LID (sem duplicar) ----
    r = run(".naovou", sender_jid=DIEGO_LID)
    assert "saiu" in r.text.lower() or "não estava" in r.text.lower(), r.text

    # ---- remover pelo nome EXATO (Nathan ≠ nathan) ----
    run(".cadastro 5511999990001 5 Nathan")
    run(".cadastro 5511999990002 5 nathan")
    r = run(".remover Nathan")
    assert "removido" in r.text.lower(), r.text
    nomes = {p.name for p in db.list_players()}
    assert "nathan" in nomes and "Nathan" not in nomes, nomes  # só o "Nathan" saiu

    # ---- pagamento em massa por menções ----
    r = run(".pagou x", mentioned=[DAVID_LID, DANIEL_LID])
    assert "2 marcado" in r.text.lower() and "💰" in r.text, r.text
    assert db.get_player(canonical_phone("100000000000001")).pagou
    assert db.get_player(canonical_phone("100000000000002")).pagou

    # aparece 💰 no .jogadores
    assert "💰" in run(".jogadores").text

    # pagou individual por nome
    r = run(".pagou Bravo")
    assert "pago" in r.text.lower(), r.text
    assert db.get_player(canonical_phone("999888777666555")).pagou

    # ---- reset zera todo mundo ----
    r = run(".resetpagamento")
    assert "zerado" in r.text.lower(), r.text
    assert not any(p.pagou for p in db.list_players())

    # ---- sorteio ----
    run(".vou", sender_jid=DIEGO_LID)
    run(".vou", sender_jid=BRAVO_LID)

    # lista aberta não pode ser sorteada
    r = run(".sorteiotimes 2")
    assert "feche a lista" in r.text.lower(), r.text
    r = run(".abrirmvp")
    assert "feche a lista" in r.text.lower(), r.text

    # somente admin pode sortear, mesmo com a lista fechada
    run(".fecharlista")
    r = run(".sorteiotimes 2", sender_jid=DIEGO_LID)
    assert "apenas o admin" in r.text.lower(), r.text

    r = run(".sorteiotimes 2")
    assert "TIMES SORTEADOS" in r.text and "Time 1" in r.text and "Time 2" in r.text, r.text

    # ---- votação de MVP: só titulares votam, voto pode ser atualizado ----
    r = run(".abrirmvp", sender_jid=DIEGO_LID)
    assert "apenas o admin" in r.text.lower(), r.text
    r = run(".abrirmvp")
    assert "votação de mvp aberta" in r.text.lower(), r.text

    r = run(".votemvp @Bravo", sender_jid=BRAVO_LID, mentioned=[BRAVO_LID])
    assert "si mesmo" in r.text.lower(), r.text
    r = run(".votemvp @Bravo", sender_jid=DIEGO_LID, mentioned=[BRAVO_LID])
    assert "computado" in r.text.lower(), r.text
    r = run(".votemvp @Daniel", sender_jid=DIEGO_LID, mentioned=[DANIEL_LID])
    assert "atualizado" in r.text.lower(), r.text
    r = run(".votemvp @Bravo", sender_jid=DIEGO_LID, mentioned=[BRAVO_LID])
    assert "atualizado" in r.text.lower(), r.text
    r = run(".votemvp @Bravo", sender_jid=DAVID_LID, mentioned=[BRAVO_LID])
    assert "computado" in r.text.lower(), r.text

    antes = db.get_player(canonical_phone("999888777666555")).overall
    r = run(".fecharmvp")
    depois = db.get_player(canonical_phone("999888777666555")).overall
    assert "mvp da pelada" in r.text.lower() and BRAVO_LID in r.mentions, r.text
    assert depois == min(10, antes + 1), (antes, depois)

    # ---- votação de Bagre: empate não altera overall ----
    r = run(".abrirbagre")
    assert "votação de bagre aberta" in r.text.lower(), r.text
    run(".votebagre @Bravo", sender_jid=DIEGO_LID, mentioned=[BRAVO_LID])
    run(".votebagre @Daniel", sender_jid=DAVID_LID, mentioned=[DANIEL_LID])
    bravo_antes = db.get_player(canonical_phone("999888777666555")).overall
    daniel_antes = db.get_player(canonical_phone("100000000000002")).overall
    r = run(".fecharbagre")
    assert "empate" in r.text.lower(), r.text
    assert db.get_player(canonical_phone("999888777666555")).overall == bravo_antes
    assert db.get_player(canonical_phone("100000000000002")).overall == daniel_antes

    # vencedor único do Bagre perde um ponto
    run(".abrirbagre")
    run(".votebagre @Bravo", sender_jid=DIEGO_LID, mentioned=[BRAVO_LID])
    run(".votebagre @Bravo", sender_jid=DAVID_LID, mentioned=[BRAVO_LID])
    antes = db.get_player(canonical_phone("999888777666555")).overall
    r = run(".fecharbagre")
    depois = db.get_player(canonical_phone("999888777666555")).overall
    assert "bagre da pelada" in r.text.lower() and BRAVO_LID in r.mentions, r.text
    assert depois == max(0, antes - 1), (antes, depois)

    # limites permanentes do overall
    db.upsert_player(canonical_phone("999888777666555"), "Bravo", 10)
    assert db.adjust_overall(canonical_phone("999888777666555"), 1).overall == 10
    db.upsert_player(canonical_phone("999888777666555"), "Bravo", 0)
    assert db.adjust_overall(canonical_phone("999888777666555"), -1).overall == 0

    # ---- nivelamento: distribui fortes e fracos entre os times ----
    notas = [9, 9, 8, 8, 8, 7, 7, 7, 6, 6, 5, 4, 4, 3, 2]
    jogadores = [teams.Jogador(f"J{i}", nota) for i, nota in enumerate(notas)]
    sorteados = teams.sortear(jogadores, 3, seed=42)
    assert all(len(t.jogadores) == 5 for t in sorteados), sorteados
    assert max(sum(j.overall >= 8 for j in t.jogadores) for t in sorteados) <= 2
    assert all(min(j.overall for j in t.jogadores) <= 4 for t in sorteados)
    assert commands._parse_num_times([], 15) == 3
    assert commands._parse_num_times([], 16) == 4

    print("OK - todos os testes passaram ✅")


if __name__ == "__main__":
    main()
