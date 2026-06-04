"""Configuração carregada de variáveis de ambiente (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


@dataclass
class Settings:
    base_url: str = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080").rstrip("/")
    instance: str = os.getenv("EVOLUTION_INSTANCE", "pelada")
    api_key: str = os.getenv("EVOLUTION_API_KEY", "")
    allowed_group_jid: str = os.getenv("ALLOWED_GROUP_JID", "").strip()
    webhook_token: str = os.getenv("WEBHOOK_TOKEN", "").strip()
    db_path: str = os.getenv("DB_PATH", "pelada.db")
    admin_numbers: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        raw = os.getenv("ADMIN_NUMBERS", "")
        self.admin_numbers = {
            _only_digits(n) for n in raw.split(",") if _only_digits(n)
        }

    def is_admin(self, phone: str) -> bool:
        return _only_digits(phone) in self.admin_numbers


settings = Settings()
