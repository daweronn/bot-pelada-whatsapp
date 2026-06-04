"""Sorteio de times equilibrados pela soma dos overalls."""
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Jogador:
    name: str
    overall: int


@dataclass
class Time:
    jogadores: list[Jogador]

    @property
    def soma(self) -> int:
        return sum(j.overall for j in self.jogadores)

    @property
    def media(self) -> float:
        return self.soma / len(self.jogadores) if self.jogadores else 0.0


def _spread(times: list[Time]) -> int:
    somas = [t.soma for t in times]
    return max(somas) - min(somas)


def sortear(jogadores: list[Jogador], num_times: int, seed: int | None = None) -> list[Time]:
    """Distribui jogadores em `num_times` times equilibrando a soma dos overalls.

    Estratégia: embaralha (pra variar entre sorteios), ordena por overall,
    distribui em serpentina e refina com trocas que reduzam a diferença
    entre o time mais forte e o mais fraco.
    """
    rng = random.Random(seed)
    pool = list(jogadores)
    rng.shuffle(pool)  # desempata de forma aleatória entre overalls iguais
    pool.sort(key=lambda j: j.overall, reverse=True)

    times = [Time([]) for _ in range(num_times)]

    # distribuição serpentina: 0,1,2,2,1,0,0,1,2...
    idx = 0
    direction = 1
    for jog in pool:
        times[idx].jogadores.append(jog)
        if num_times == 1:
            continue
        if direction == 1 and idx == num_times - 1:
            direction = -1
        elif direction == -1 and idx == 0:
            direction = 1
        else:
            idx += direction

    # refino: tenta trocar jogadores entre o time mais forte e o mais fraco
    for _ in range(200):
        if _spread(times) == 0:
            break
        forte = max(times, key=lambda t: t.soma)
        fraco = min(times, key=lambda t: t.soma)
        if forte is fraco:
            break
        atual = _spread(times)
        melhor = None  # (novo_spread, jf, jw)
        for jf in forte.jogadores:
            for jw in fraco.jogadores:
                diff = jf.overall - jw.overall
                if diff <= 0:
                    continue  # só troca que aproxima
                nova_forte = forte.soma - diff
                nova_fraco = fraco.soma + diff
                novo_spread = abs(nova_forte - nova_fraco)
                if novo_spread < atual and (melhor is None or novo_spread < melhor[0]):
                    melhor = (novo_spread, jf, jw)
        if melhor is None:
            break
        _, jf, jw = melhor
        forte.jogadores.remove(jf)
        fraco.jogadores.remove(jw)
        forte.jogadores.append(jw)
        fraco.jogadores.append(jf)

    return times
