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


def carregar() -> Settings:
    return Settings(
        database_url=_obrigatoria("DATABASE_URL"),
        database_pool_max=int(os.getenv("DATABASE_POOL_MAX", "5")),
        evolution_base_url=_obrigatoria("EVOLUTION_BASE_URL").rstrip("/"),
        evolution_instance=_obrigatoria("EVOLUTION_INSTANCE"),
        evolution_api_key=_obrigatoria("EVOLUTION_API_KEY"),
        webhook_token=os.getenv("WEBHOOK_TOKEN", "").strip(),
        default_overall=int(os.getenv("DEFAULT_OVERALL", "5")),
        debug_payload=os.getenv("DEBUG_PAYLOAD", "").strip().lower() in {"1", "true", "yes"},
    )


settings = carregar()
