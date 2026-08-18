"""Normalização de telefone — resolve o problema do 9º dígito brasileiro.

No WhatsApp, um mesmo número pode chegar com ou sem o 9 do celular
(ex.: 5522998720569 vs 552298720569). Pra comparar/identificar de forma
confiável, reduzimos tudo a uma chave canônica: 55 + DDD + últimos 8 dígitos.

Essa chave identifica, mas NÃO disca: o 9º dígito descartado não é
recuperável. Para enviar mensagem use sempre o phone_jid original.
"""
from __future__ import annotations


def only_digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def canonical_phone(raw: str) -> str:
    """Devolve uma chave canônica do número, à prova do 9º dígito.

    - '5522998720569' (com 9)  -> '552298720569'
    - '552298720569'  (sem 9)  -> '552298720569'
    - '22998720569'   (sem DDI)-> '552298720569'
    Números fora do padrão BR voltam só com os dígitos.
    """
    d = only_digits(raw)
    if not d:
        return ""

    if len(d) in (10, 11) and not d.startswith("55"):
        d = "55" + d

    if d.startswith("55") and len(d) in (12, 13):
        ddd = d[2:4]
        local8 = d[4:][-8:]
        return "55" + ddd + local8

    return d
