"""Configuração carregada de variáveis de ambiente (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _obrigatoria(nome: str) -> str:
    valor = os.getenv(nome, "").strip()
    if not valor:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {nome}")
    return valor


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_pool_max: int
    evolution_base_url: str
    evolution_instance: str
    evolution_api_key: str
    webhook_token: str
    default_overall: int
    debug_payload: bool
    fila_intervalo_min_s: float
    fila_intervalo_max_s: float
    fila_ociosa_s: int
    fila_max_tentativas: int
    fila_espera_base_s: int
    fila_lease_s: int


# O lease precisa passar com folga do timeout HTTP de 15 s da Evolution, senão
# outra instância reserva o envio ainda em voo e manda duas vezes.
_LEASE_MINIMO_S = 60


def _positivo(nome: str, padrao: str, tipo: type[int] | type[float]) -> int | float:
    valor = tipo(os.getenv(nome, padrao))
    if valor <= 0:
        raise RuntimeError(f"{nome} precisa ser maior que zero (recebido {valor})")
    return valor


def carregar() -> Settings:
    intervalo_min = _positivo("FILA_INTERVALO_MIN_S", "8", float)
    intervalo_max = _positivo("FILA_INTERVALO_MAX_S", "20", float)
    if intervalo_min > intervalo_max:
        raise RuntimeError(
            f"FILA_INTERVALO_MIN_S ({intervalo_min}) não pode ser maior que FILA_INTERVALO_MAX_S ({intervalo_max})"
        )
    lease = _positivo("FILA_LEASE_S", "120", int)
    if lease < _LEASE_MINIMO_S:
        raise RuntimeError(f"FILA_LEASE_S precisa ser pelo menos {_LEASE_MINIMO_S} (recebido {lease})")
    return Settings(
        database_url=_obrigatoria("DATABASE_URL"),
        database_pool_max=int(os.getenv("DATABASE_POOL_MAX", "5")),
        evolution_base_url=_obrigatoria("EVOLUTION_BASE_URL").rstrip("/"),
        evolution_instance=_obrigatoria("EVOLUTION_INSTANCE"),
        evolution_api_key=_obrigatoria("EVOLUTION_API_KEY"),
        webhook_token=_obrigatoria("WEBHOOK_TOKEN"),
        default_overall=int(os.getenv("DEFAULT_OVERALL", "5")),
        debug_payload=os.getenv("DEBUG_PAYLOAD", "").strip().lower() in {"1", "true", "yes"},
        fila_intervalo_min_s=intervalo_min,
        fila_intervalo_max_s=intervalo_max,
        fila_ociosa_s=_positivo("FILA_OCIOSA_S", "10", int),
        fila_max_tentativas=_positivo("FILA_MAX_TENTATIVAS", "4", int),
        fila_espera_base_s=_positivo("FILA_ESPERA_BASE_S", "30", int),
        fila_lease_s=lease,
    )


settings = carregar()
