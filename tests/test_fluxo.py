"""Fluxo completo contra o Postgres real, num grupo descartável.

Roda: python -m tests.test_fluxo
"""
from __future__ import annotations

from app.phones import canonical_phone
from app.repositories import membros, rodadas

from . import fixtures
from .fixtures import executar_comando as cmd

DIEGO_LID = "111222333444555@lid"
BRAVO_LID = "999888777666555@lid"
CARLOS_LID = "222333444555666@lid"
CARLOS_FONE = "5522987654321@s.whatsapp.net"
DAVID_LID = "100000000000001@lid"
DANIEL_LID = "100000000000002@lid"


def _membro(lid_ou_fone: str):
    chave = canonical_phone(lid_ou_fone.split("@", 1)[0])
    return membros.por_identidade(fixtures.grupo_id(), [chave])


def cadastro_e_identidade() -> None:
    resposta = cmd(".cadastro 5511111111111 8 Alfa")
    assert "Alfa" in resposta.text and "🚫" not in resposta.text, resposta.text

    resposta = cmd(".sorteiotimes", remetente=DIEGO_LID)
    assert "apenas o admin" in resposta.text.lower(), resposta.text

    cmd(".abrirlista 15")
    resposta = cmd(".vou", remetente=DIEGO_LID, apelido="Diego")
    assert "confirmada" in resposta.text.lower(), resposta.text
    diego = _membro(DIEGO_LID)
    assert diego and diego.nome == "Diego" and diego.overall == 5, diego
    assert diego.phone_jid is None and diego.lid, diego

    resposta = cmd(".cadastro Diego 9")
    assert "atualizado" in resposta.text.lower() and "9/10" in resposta.text, resposta.text
    assert _membro(DIEGO_LID).overall == 9

    cmd(".cadastro 7 Bravo", mencionados=[BRAVO_LID])
    cmd(".vou", remetente=BRAVO_LID, apelido="Bravo")
    assert _membro(BRAVO_LID).overall == 7, "menção e .vou têm que casar pelo LID"


def fusao_de_identidade() -> None:
    cmd(".cadastro 6 Carlos", mencionados=[CARLOS_LID])
    cmd("bom dia", remetente=CARLOS_LID, telefone=CARLOS_FONE, apelido="Carlos")

    carlos = _membro(CARLOS_FONE)
    assert carlos and carlos.overall == 6, carlos
    assert carlos.phone_jid == CARLOS_FONE, "o JID discável tem que ser guardado inteiro"
    assert _membro(CARLOS_LID) is None, "o cadastro do LID tinha que ter sido fundido"

    cmd(".cadastro 5522987654321 9 Carlos")
    assert _membro(CARLOS_FONE).overall == 9
    achados = [m for m in membros.listar_todos(fixtures.grupo_id()) if m.nome == "Carlos"]
    assert len(achados) == 1, achados


def mensalistas_e_lista() -> None:
    resposta = cmd(".mensalista x", mencionados=[DAVID_LID, DANIEL_LID, DIEGO_LID])
    assert "3 marcado" in resposta.text.lower(), resposta.text
    assert _membro(DAVID_LID).mensalista

    cmd(".abrirlista 15")
    cmd(".vou", remetente=DAVID_LID, apelido="David")
    davids = [m for m in membros.listar_todos(fixtures.grupo_id()) if m.nome == "David"]
    assert len(davids) == 1 and davids[0].mensalista, davids

    rodada = rodadas.aberta(fixtures.grupo_id())
    presentes = rodadas.presencas(rodada.id)
    assert {p.nome for p in presentes} >= {"David", "Diego"}, presentes

    resposta = cmd(".naovou", remetente=DIEGO_LID)
    assert "saiu" in resposta.text.lower(), resposta.text

    cmd(".cadastro 5511999990001 5 Nathan")
    cmd(".cadastro 5511999990002 5 nathan")
    resposta = cmd(".remover Nathan")
    assert "removido" in resposta.text.lower(), resposta.text
    nomes = {m.nome for m in membros.listar_todos(fixtures.grupo_id())}
    assert "nathan" in nomes and "Nathan" not in nomes, nomes


def sorteio_e_votacoes() -> None:
    cmd(".vou", remetente=DIEGO_LID)
    cmd(".vou", remetente=BRAVO_LID)

    resposta = cmd(".sorteiotimes 2")
    assert "feche a lista" in resposta.text.lower(), resposta.text
    resposta = cmd(".abrirmvp")
    assert "feche a lista" in resposta.text.lower(), resposta.text

    cmd(".fecharlista")
    resposta = cmd(".sorteiotimes 2")
    assert "TIMES SORTEADOS" in resposta.text and "Time 2" in resposta.text, resposta.text

    assert "aberta" in cmd(".abrirmvp").text.lower()
    resposta = cmd(".votemvp @Bravo", remetente=BRAVO_LID, mencionados=[BRAVO_LID])
    assert "si mesmo" in resposta.text.lower(), resposta.text
    resposta = cmd(".votemvp @Bravo", remetente=DIEGO_LID, mencionados=[BRAVO_LID])
    assert "computado" in resposta.text.lower(), resposta.text
    resposta = cmd(".votemvp @David", remetente=DIEGO_LID, mencionados=[DAVID_LID])
    assert "atualizado" in resposta.text.lower(), resposta.text
    cmd(".votemvp @Bravo", remetente=DIEGO_LID, mencionados=[BRAVO_LID])
    cmd(".votemvp @Bravo", remetente=DAVID_LID, mencionados=[BRAVO_LID])

    antes = _membro(BRAVO_LID).overall
    resposta = cmd(".fecharmvp")
    assert "mvp da pelada" in resposta.text.lower(), resposta.text
    assert _membro(BRAVO_LID).overall == min(10, antes + 1)

    cmd(".abrirbagre")
    cmd(".votebagre @Bravo", remetente=DIEGO_LID, mencionados=[BRAVO_LID])
    resposta = cmd(".votebagre @Diego", remetente=DAVID_LID, mencionados=[DIEGO_LID])
    assert "computado" in resposta.text.lower(), resposta.text
    bravo_antes = _membro(BRAVO_LID).overall
    diego_antes = _membro(DIEGO_LID).overall
    resposta = cmd(".fecharbagre")
    assert "empate" in resposta.text.lower(), resposta.text
    assert _membro(BRAVO_LID).overall == bravo_antes
    assert _membro(DIEGO_LID).overall == diego_antes


def isolamento_entre_grupos() -> None:
    from app.repositories import grupos

    assert grupos.por_jid("000000000000000000@g.us") is None
    assert grupos.e_admin(fixtures.grupo_id(), ["552299999999"]) is False
    assert grupos.e_admin(fixtures.grupo_id(), [canonical_phone("5522998720569")]) is True


def main() -> None:
    fixtures.criar_grupo()
    try:
        cadastro_e_identidade()
        fusao_de_identidade()
        mensalistas_e_lista()
        sorteio_e_votacoes()
        isolamento_entre_grupos()
        print("OK - todos os testes passaram")
    finally:
        fixtures.apagar_grupo()


if __name__ == "__main__":
    main()
