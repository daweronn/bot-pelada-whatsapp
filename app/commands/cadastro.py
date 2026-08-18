"""Comandos de cadastro: jogadores, notas e tipo de vínculo."""
from __future__ import annotations

from ..config import settings
from ..models import e_nome_provisorio, nome_provisorio
from ..repositories import membros
from . import alvos, renderizacao
from .contexto import Contexto, Reply, apenas_admin

_EXEMPLOS = (
    "_Use uma destas formas:_\n"
    "• `.cadastro @Fulano 7 Fulano` _(marca a pessoa — recomendado p/ .vou funcionar)_\n"
    "• `.cadastro 5522998720569 7 Fulano` _(por número)_\n"
    "• `.cadastro Fulano 8` _(ajusta a nota de quem já apareceu)_"
)


def cadastrar(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("cadastrar jogadores")

    alvo, resto = alvos.identificar(ctx, ctx.args)
    overall, resto = alvos.extrair_overall(resto)
    nome = alvos.juntar_nome(resto)

    if alvo:
        atual = membros.por_identidade(ctx.grupo.id, [alvo.identity_key])
        if overall is None:
            return Reply(f"❓ Faltou a *nota* (de 0 a 10).\n{_EXEMPLOS}")
        if not nome:
            if not atual:
                return Reply(f"❓ Faltou o *nome* do jogador.\n{_EXEMPLOS}")
            nome = atual.nome
        membro, criado = membros.salvar(
            ctx.grupo.id, alvo.identity_key, nome, overall,
            phone_jid=alvo.phone_jid, lid=alvo.lid,
        )
        titulo = "Jogador cadastrado" if criado else "Cadastro atualizado"
        aviso = "" if membro.phone_jid else f"\n{renderizacao.SEM_NUMERO} _Sem número capturado ainda._"
        return Reply(f"✅ *{titulo}!*\n👤 {membro.nome}\n🎯 Overall: *{membro.overall}/10*{aviso}")

    if not nome:
        return Reply(f"❓ Não entendi o jogador.\n{_EXEMPLOS}")
    if overall is None:
        return Reply(f"❓ Pra ajustar pelo nome, informe a nota. Ex.: `.cadastro {nome} 8`")

    encontrados = membros.buscar_por_nome(ctx.grupo.id, nome)
    if not encontrados:
        return Reply(
            f"❓ Não achei *{nome}* cadastrado.\n"
            "Peça pra pessoa mandar *.vou*, ou cadastre com *@menção* / número."
        )
    if len(encontrados) > 1:
        nomes = ", ".join(m.nome for m in encontrados[:6])
        return Reply(f"⚠️ Mais de um parecido: {nomes}. Use *@menção* ou número.")

    alvo_nome = encontrados[0]
    membro, _ = membros.salvar(ctx.grupo.id, alvo_nome.identity_key, alvo_nome.nome, overall)
    return Reply(f"✅ *Cadastro atualizado!*\n👤 {membro.nome}\n🎯 Overall: *{membro.overall}/10*")


def remover(ctx: Contexto) -> Reply:
    if not ctx.admin:
        return apenas_admin("remover jogadores")
    membro, erro = alvos.membro_existente(ctx, ctx.args)
    if erro:
        return erro
    membros.remover(ctx.grupo.id, membro.identity_key)
    return Reply(f"🗑️ *{membro.nome}* removido da pelada.")


def definir_tipo(ctx: Contexto, mensalista: bool) -> Reply:
    if not ctx.admin:
        return apenas_admin("alterar mensalistas")

    emoji = renderizacao.MENSALISTA if mensalista else renderizacao.DIARISTA
    rotulo = "mensalista" if mensalista else "diarista"

    marcados = alvos.mencoes(ctx)
    if marcados:
        return _definir_tipo_em_massa(ctx, marcados, mensalista, emoji, rotulo)

    membro, erro = alvos.membro_existente(ctx, ctx.args)
    if erro:
        return erro
    membros.definir_mensalista(ctx.grupo.id, membro.identity_key, mensalista)
    if mensalista:
        return Reply(f"{emoji} *{membro.nome}* agora é *mensalista* — vaga garantida em toda lista.")
    return Reply(f"{emoji} *{membro.nome}* agora é *diarista* (avulso).")


def _definir_tipo_em_massa(
    ctx: Contexto, marcados: list[alvos.Alvo], mensalista: bool, emoji: str, rotulo: str
) -> Reply:
    feitos: list[str] = []
    for alvo in marcados:
        atual = membros.por_identidade(ctx.grupo.id, [alvo.identity_key])
        if atual:
            membros.definir_mensalista(ctx.grupo.id, alvo.identity_key, mensalista)
            feitos.append(atual.nome)
        elif mensalista:
            nome = nome_provisorio(alvo.identity_key)
            membros.salvar(
                ctx.grupo.id, alvo.identity_key, nome, settings.default_overall,
                mensalista=True, phone_jid=alvo.phone_jid, lid=alvo.lid,
            )
            feitos.append(nome)

    if not feitos:
        return Reply("❓ Não consegui marcar ninguém. Tente mencionar de novo.")
    linhas = [f"{emoji} *{len(feitos)} marcado(s) como {rotulo}:*"]
    linhas += [f"{emoji} {nome}" for nome in feitos]
    if any(e_nome_provisorio(nome) for nome in feitos):
        linhas.append("\n_O nome se ajusta sozinho quando a pessoa mandar *.vou*._")
    return Reply("\n".join(linhas))


def listar(ctx: Contexto) -> Reply:
    return Reply(renderizacao.elenco(membros.listar_todos(ctx.grupo.id)))
