"""Sorteio de times nivelados por faixas de overall."""
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


def sortear(jogadores: list[Jogador], num_times: int, seed: int | None = None) -> list[Time]:
    """Distribui por faixas, dando a cada time um jogador de cada nível.

    Os jogadores são ordenados e separados em rodadas do tamanho da quantidade
    de times. Em cada rodada, cada time recebe no máximo um jogador. Isso evita
    concentrar vários jogadores fortes em um time e compensar apenas com notas
    baixas. Dentro de cada faixa, o melhor disponível vai para o time cuja
    composição acumulada está mais fraca.
    """
    if num_times < 1:
        raise ValueError("num_times deve ser pelo menos 1")
    if not jogadores:
        return []

    rng = random.Random(seed)
    pool = list(jogadores)
    rng.shuffle(pool)  # varia apenas o desempate entre jogadores de mesma nota
    pool.sort(key=lambda j: j.overall, reverse=True)

    num_times = min(num_times, len(pool))
    times = [Time([]) for _ in range(num_times)]
    desempate = list(range(num_times))
    rng.shuffle(desempate)
    prioridade = {team_idx: pos for pos, team_idx in enumerate(desempate)}

    for inicio in range(0, len(pool), num_times):
        faixa = pool[inicio : inicio + num_times]
        mais_fracos = sorted(
            range(num_times),
            key=lambda i: (times[i].soma, len(times[i].jogadores), prioridade[i]),
        )
        for jogador, team_idx in zip(faixa, mais_fracos):
            times[team_idx].jogadores.append(jogador)

    return times
