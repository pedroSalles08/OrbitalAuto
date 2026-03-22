from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Final

from fastapi import Request

from config import BASIC_AUTH_PASS, BASIC_AUTH_USER

ACCESS_COOKIE_NAME: Final[str] = "orbital_access"


def access_gate_enabled() -> bool:
    """Retorna True quando a barreira simples por senha esta habilitada."""
    return bool(BASIC_AUTH_USER and BASIC_AUTH_PASS)


def verify_access_credentials(username: str, password: str) -> bool:
    """Valida as credenciais da barreira simples."""
    if not access_gate_enabled():
        return True

    return (
        secrets.compare_digest(username, BASIC_AUTH_USER)
        and secrets.compare_digest(password, BASIC_AUTH_PASS)
    )


def build_access_cookie_value() -> str:
    """Gera um cookie assinado sem armazenamento server-side."""
    username = BASIC_AUTH_USER
    signature = hmac.new(
        BASIC_AUTH_PASS.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{username}:{signature}"


def has_valid_access_cookie(cookie_value: str | None) -> bool:
    """Valida o cookie da barreira simples."""
    if not access_gate_enabled():
        return True

    if not cookie_value or ":" not in cookie_value:
        return False

    username, signature = cookie_value.split(":", 1)
    expected = hmac.new(
        BASIC_AUTH_PASS.encode("utf-8"),
        username.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return (
        secrets.compare_digest(username, BASIC_AUTH_USER)
        and secrets.compare_digest(signature, expected)
    )


def access_cookie_settings(request: Request) -> dict[str, object]:
    """Configuracao unica do cookie de acesso."""
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return {
        "key": ACCESS_COOKIE_NAME,
        "value": build_access_cookie_value(),
        "httponly": True,
        "samesite": "lax",
        "secure": forwarded_proto == "https",
        "path": "/",
    }
