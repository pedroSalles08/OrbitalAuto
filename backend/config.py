# ── OrbitalAuto · Configuração ────────────────────────────────────
"""
Carrega variáveis de ambiente do .env e expõe como constantes.
Em DESKTOP_MODE o app funciona standalone sem .env.
"""

import os
import sys
from dotenv import load_dotenv

# Em modo desktop (PyInstaller) não precisa de .env, mas carrega se existir
load_dotenv(override=False)


# ── Desktop Mode ──────────────────────────────────────────────────

DESKTOP_MODE: bool = (
    getattr(sys, "frozen", False)  # PyInstaller bundle
    or os.getenv("DESKTOP_MODE", "false").lower() in ("true", "1", "yes")
)

# ── Orbital ───────────────────────────────────────────────────────

ORBITAL_BASE_URL: str = os.getenv("ORBITAL_BASE_URL", "https://orbital.iffarroupilha.edu.br")

# ── Sessões ───────────────────────────────────────────────────────

SESSION_EXPIRY_HOURS: int = int(os.getenv("SESSION_EXPIRY_HOURS", "4"))
MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "1" if DESKTOP_MODE else "100"))

# ── CORS ──────────────────────────────────────────────────────────

# No desktop mode, frontend is served from same origin — no CORS needed
_default_origins = "*" if DESKTOP_MODE else "http://localhost:3000"
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")
    if o.strip()
]

# ── Servidor ──────────────────────────────────────────────────────

PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
