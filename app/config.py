"""Configuração carregada de variáveis de ambiente (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

from .phones import canonical_phone, only_digits

load_dotenv()


@dataclass
class Settings:
    base_url: str = os.getenv("EVOLUTION_BASE_URL", "http://localhost:8080").rstrip("/")
    instance: str = os.getenv("EVOLUTION_INSTANCE", "pelada")
    api_key: str = os.getenv("EVOLUTION_API_KEY", "")
    allowed_group_jid: str = os.getenv("ALLOWED_GROUP_JID", "").strip()
    webhook_token: str = os.getenv("WEBHOOK_TOKEN", "").strip()
    db_path: str = os.getenv("DB_PATH", "pelada.db")
    debug_payload: bool = os.getenv("DEBUG_PAYLOAD", "").strip().lower() in {"1", "true", "yes"}
    default_overall: int = int(os.getenv("DEFAULT_OVERALL", "5"))
    admin_numbers: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        raw = os.getenv("ADMIN_NUMBERS", "")
        # guarda os admins já na forma canônica (à prova do 9º dígito)
        self.admin_numbers = {
            canonical_phone(n) for n in raw.split(",") if only_digits(n)
        }

    def is_admin(self, phone: str) -> bool:
        return canonical_phone(phone) in self.admin_numbers


settings = Settings()
