"""Texto de ajuda do bot."""
from __future__ import annotations

from . import renderizacao
from .contexto import Contexto, Reply

_LINHA = renderizacao.LINHA


def ajuda(_ctx: Contexto) -> Reply:
    return Reply(
        "⚽ *BOT DA PELADA* ⚽\n"
        "_Cadastro, lista de presença e sorteio de times._\n"
        f"{_LINHA}\n"
        "👤 *JOGADORES* _(admin)_\n"
        "• *.cadastro* _@pessoa nota nome_  ↳ recomendado 👈\n"
        "   ↳ marcar com @ liga o cadastro ao *.vou* da pessoa\n"
        "   ↳ _ex.: .cadastro @João 7 João_\n"
        "   ↳ também: `.cadastro 5522998720569 7 João` ou `.cadastro João 8`\n"
        "• *.remover* _@pessoa/número/nome_\n"
        f"• *.mensalista* _@um @dois @três_  ↳ marca vários de uma vez {renderizacao.MENSALISTA}\n"
        f"• *.diarista* _@pessoa/número/nome_  ↳ vira avulso {renderizacao.DIARISTA}\n"
        "• *.jogadores*  ↳ lista todos os cadastrados\n"
        f"{_LINHA}\n"
        "📝 *LISTA DA PELADA*\n"
        "• *.abrirlista* _[vagas]_  ↳ abre e já inclui os mensalistas _(admin)_\n"
        "• *.vou*  ↳ confirmo minha presença ✅\n"
        "• *.naovou*  ↳ saio da lista\n"
        "• *.vai* _@/número nota nome_  ↳ _(admin)_ cadastra e já põe na lista\n"
        "• *.naovai* _@/número/nome_  ↳ _(admin)_ tira alguém da lista\n"
        "• *.lista*  ↳ mostra titulares + espera\n"
        "• *.fecharlista*  ↳ fecha _(admin)_\n"
        f"{_LINHA}\n"
        "🎲 *SORTEIO* _(admin e somente com a lista fechada)_\n"
        "• *.sorteiotimes*  ↳ times nivelados _(padrão: até 5/time)_\n"
        "• *.sorteiotimes 4*  ↳ força 4 times\n"
        "• *.sorteiotimes t6*  ↳ 6 jogadores por time\n"
        f"{_LINHA}\n"
        "🏆 *VOTAÇÕES* _(lista fechada)_\n"
        "• *.abrirmvp* / *.fecharmvp*  ↳ admin abre/fecha o MVP\n"
        "• *.votemvp @jogador*  ↳ vencedor ganha +1 overall _(máx. 10)_\n"
        "• *.abrirbagre* / *.fecharbagre*  ↳ admin abre/fecha o Bagre\n"
        "• *.votebagre @jogador*  ↳ vencedor perde -1 overall _(mín. 0)_\n"
        f"{_LINHA}\n"
        "💡 *Como funciona a vaga:*\n"
        f"{renderizacao.MENSALISTA} Mensalista entra automático; só sai se mandar *.naovou*.\n"
        f"{renderizacao.DIARISTA} Diarista manda *.vou*; sem cadastro, entra com nota média.\n"
        "⬆️ Se um titular sai, o 1º da espera sobe sozinho.\n"
        f"{renderizacao.SEM_NUMERO} _Marca quem ainda não teve o número capturado._"
    )
