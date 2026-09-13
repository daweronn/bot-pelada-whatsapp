"""Fila de mensagens contra o Postgres real, só com mensagens do grupo descartável.

Roda: python -m tests.test_fila
Rode com o bot de produção parado: senão ele pode reservar as linhas do teste e o
teste falha à toa (sem dano aos dados reais).
"""
from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from app import fila
from app.commands import noticia
from app.commands.contexto import Contexto
from app.config import settings
from app.database import executar, transacao
from app.messages import parse_event
from app.models import Grupo
from app.repositories import envios, mensagens

from . import fixtures

_criadas: list[UUID] = []
SEM_DESTINO = "Nenhum grupo ativo no destino."


def _consultar(sql: str, params: tuple) -> tuple:
    with transacao() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def _criar_mensagem(escopo: str = "grupo", **destino: UUID | None) -> UUID:
    texto = f"teste fila {uuid4()}"
    mensagens.enfileirar(escopo, texto, **(destino or {"grupo_id": fixtures.grupo_id()}))
    (mensagem_id,) = _consultar("SELECT id FROM pelada.mensagens WHERE texto = %s", (texto,))
    _criadas.append(mensagem_id)
    return mensagem_id


def _envio(mensagem_id: UUID) -> tuple:
    return _consultar(
        "SELECT status::text, tentativas, erro FROM pelada.mensagem_envios WHERE mensagem_id = %s",
        (mensagem_id,),
    )


def _mensagem(mensagem_id: UUID) -> tuple:
    return _consultar(
        "SELECT status::text, erro, enviado_em IS NOT NULL FROM pelada.mensagens WHERE id = %s",
        (mensagem_id,),
    )


def _fila_alheia_vazia() -> None:
    # O teste roda na fila de produção: com trabalho alheio vencido, ele poderia reservá-lo.
    (alheios,) = _consultar(
        """
        SELECT (SELECT count(*) FROM pelada.mensagens
                WHERE status = 'pendente' AND distribuida_em IS NULL
                  AND (agendar_para IS NULL OR agendar_para <= now()))
             + (SELECT count(*) FROM pelada.mensagem_envios
                WHERE status = 'pendente' AND proxima_tentativa <= now())
        """,
        (),
    )
    if alheios:
        raise SystemExit(f"Fila com {alheios} item(ns) alheio(s) pendente(s); rode o teste depois.")


def _remetente(falhar: bool, chamadas: list[tuple[str, str]]):
    async def enviar(jid: str, texto: str) -> None:
        # Recusa JID alheio: um envio real reservado por engano volta reagendado, nunca "enviado".
        if jid != fixtures.GRUPO_JID:
            raise RuntimeError(f"envio alheio ao teste: {jid}")
        chamadas.append((jid, texto))
        if falhar:
            raise RuntimeError("falha simulada")

    return enviar


def envio_com_sucesso() -> None:
    mensagem_id = _criar_mensagem()
    chamadas: list[tuple[str, str]] = []
    assert asyncio.run(fila.processar_uma_vez(_remetente(False, chamadas), mensagem_id)) is True
    assert [jid for jid, _ in chamadas] == [fixtures.GRUPO_JID], chamadas
    assert _envio(mensagem_id)[0] == "enviado", _envio(mensagem_id)
    assert _mensagem(mensagem_id) == ("enviado", None, True), _mensagem(mensagem_id)


def envio_com_falha() -> None:
    mensagem_id = _criar_mensagem()
    chamadas: list[tuple[str, str]] = []
    for tentativa in range(1, settings.fila_max_tentativas + 1):
        assert asyncio.run(fila.processar_uma_vez(_remetente(True, chamadas), mensagem_id)) is True
        status, tentativas, erro = _envio(mensagem_id)
        assert tentativas == tentativa and erro and "falha simulada" in erro, (status, tentativas, erro)
        if tentativa < settings.fila_max_tentativas:
            assert status == "pendente", status
            assert _mensagem(mensagem_id)[0] == "pendente", _mensagem(mensagem_id)
            (futura,) = _consultar(
                "SELECT proxima_tentativa > now() FROM pelada.mensagem_envios WHERE mensagem_id = %s",
                (mensagem_id,),
            )
            assert futura, "falha tinha que reagendar para o futuro"
            with transacao() as conn:
                executar(
                    conn,
                    "UPDATE pelada.mensagem_envios SET proxima_tentativa = now() WHERE mensagem_id = %s",
                    (mensagem_id,),
                )
    assert len(chamadas) == settings.fila_max_tentativas, chamadas
    assert _envio(mensagem_id)[0] == "erro", _envio(mensagem_id)
    status, erro, com_enviado_em = _mensagem(mensagem_id)
    assert status == "erro" and erro.startswith("Falhou em 1 de 1"), (status, erro)
    assert not com_enviado_em, "mensagem com erro não tem enviado_em"


def lease_bloqueia_segunda_reserva() -> None:
    mensagem_id = _criar_mensagem()
    mensagens.distribuir()
    envio = envios.reservar_proximo(settings.fila_lease_s, mensagem_id)
    assert envio is not None and envio.mensagem_id == mensagem_id, envio
    assert envios.reservar_proximo(settings.fila_lease_s, mensagem_id) is None, "o lease tinha que travar o envio"


def mensagem_sem_destino() -> None:
    # grupo_id/arena_id nulos não casam com nenhum grupo real (g.id = NULL nunca é verdade).
    for escopo, destino in (("grupo", {"grupo_id": None}), ("arena", {"arena_id": None})):
        mensagem_id = _criar_mensagem(escopo, **destino)
        mensagens.distribuir()
        assert _mensagem(mensagem_id) == ("erro", SEM_DESTINO, False), (escopo, _mensagem(mensagem_id))
        assert _envio(mensagem_id) is None, _envio(mensagem_id)


def envios_apagados_em_cascata() -> None:
    mensagem_id = _criar_mensagem()
    mensagens.distribuir()
    with transacao() as conn:
        executar(conn, "DELETE FROM pelada.mensagem_envios WHERE mensagem_id = %s", (mensagem_id,))
    mensagens.concluir()
    assert _mensagem(mensagem_id) == ("erro", SEM_DESTINO, False), _mensagem(mensagem_id)


def noticia_restrita_a_arena() -> None:
    capturadas: list[tuple] = []
    original = mensagens.enfileirar
    mensagens.enfileirar = lambda *args, **kwargs: capturadas.append((args, kwargs))
    try:
        # Remetente por telefone: um LID entraria na limpeza de identity_links do fixture.
        msg = parse_event(fixtures.evento(".noticia Jogo cancelado", remetente=fixtures.ADMIN_PHONE))
        arena_id = uuid4()

        def ctx(arena: UUID | None) -> Contexto:
            grupo = Grupo(uuid4(), "1@g.us", "Principal", 15, principal=True, arena_id=arena)
            return Contexto(grupo=grupo, msg=msg, identidades=[], admin=True, args=["Jogo", "cancelado"])

        resposta = noticia.noticia(ctx(arena_id))
        assert "da arena" in resposta.text, resposta.text
        assert capturadas == [(("arena", "Jogo cancelado"), {"arena_id": arena_id})], capturadas

        capturadas.clear()
        resposta = noticia.noticia(ctx(None))
        assert resposta.text == "🚫 Este grupo não está vinculado a uma arena.", resposta.text
        assert capturadas == [], capturadas
    finally:
        mensagens.enfileirar = original


def main() -> None:
    fixtures.criar_grupo()
    try:
        try:
            _fila_alheia_vazia()
            envio_com_sucesso()
            envio_com_falha()
            lease_bloqueia_segunda_reserva()
            mensagem_sem_destino()
            envios_apagados_em_cascata()
            noticia_restrita_a_arena()
            print("OK - todos os testes da fila passaram")
        finally:
            with transacao() as conn:
                executar(
                    conn,
                    "DELETE FROM pelada.mensagens WHERE grupo_id = %s OR id = ANY(%s)",
                    (fixtures.grupo_id(), _criadas),
                )
    finally:
        fixtures.apagar_grupo()


if __name__ == "__main__":
    main()
