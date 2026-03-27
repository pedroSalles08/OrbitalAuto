"""
Application configuration loaded from environment variables.

In desktop mode the app can still run without a .env file, but if one exists
it is loaded for convenience.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(override=False)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"true", "1", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _get_csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return tuple(values)


def _get_digits(name: str) -> str:
    raw = os.getenv(name, "")
    return "".join(ch for ch in raw if ch.isdigit())


DESKTOP_MODE: bool = (
    getattr(sys, "frozen", False)
    or _get_bool("DESKTOP_MODE", False)
)


ORBITAL_BASE_URL: str = os.getenv(
    "ORBITAL_BASE_URL",
    "https://orbital.iffarroupilha.edu.br",
).strip()


SESSION_EXPIRY_HOURS: int = _get_int("SESSION_EXPIRY_HOURS", 4)
MAX_SESSIONS: int = _get_int("MAX_SESSIONS", 1 if DESKTOP_MODE else 100)


BASIC_AUTH_USER: str = os.getenv("BASIC_AUTH_USER", "").strip()
BASIC_AUTH_PASS: str = os.getenv("BASIC_AUTH_PASS", "")
ENABLE_DEBUG_ROUTES: bool = _get_bool("ENABLE_DEBUG_ROUTES", False)

if bool(BASIC_AUTH_USER) != bool(BASIC_AUTH_PASS):
    raise RuntimeError(
        "BASIC_AUTH_USER and BASIC_AUTH_PASS must be set together, or both empty."
    )


AUTO_SCHEDULE_ENABLED: bool = _get_bool("AUTO_SCHEDULE_ENABLED", False)
AUTO_SCHEDULE_DRY_RUN: bool = _get_bool("AUTO_SCHEDULE_DRY_RUN", True)
AUTO_SCHEDULE_TIMEZONE: str = os.getenv(
    "AUTO_SCHEDULE_TIMEZONE",
    "America/Sao_Paulo",
).strip() or "America/Sao_Paulo"
AUTO_SCHEDULE_LOOKAHEAD_DAYS: int = _get_int(
    "AUTO_SCHEDULE_LOOKAHEAD_DAYS",
    7,
)
AUTO_SCHEDULE_CPF: str = _get_digits("AUTO_SCHEDULE_CPF")
AUTO_SCHEDULE_PASSWORD: str = os.getenv("AUTO_SCHEDULE_PASSWORD", "")
AUTO_SCHEDULE_CONFIG_PATH: str = os.getenv(
    "AUTO_SCHEDULE_CONFIG_PATH",
    str(Path(__file__).resolve().parent / "data" / "auto_schedule.json"),
).strip()
AUTO_SCHEDULE_STORE_PATH: str = os.getenv(
    "AUTO_SCHEDULE_STORE_PATH",
    str(Path(__file__).resolve().parent / "data" / "auto_schedule_profiles.json"),
).strip()
AUTO_SCHEDULE_ENCRYPTION_KEY: str = os.getenv(
    "AUTO_SCHEDULE_ENCRYPTION_KEY",
    "",
).strip()


_default_origins = "*" if DESKTOP_MODE else "http://localhost:3000"
ALLOWED_ORIGINS: list[str] = [
    value.strip()
    for value in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
    if value.strip()
]


PORT: int = _get_int("PORT", 8000)
DEBUG: bool = _get_bool("DEBUG", False)
