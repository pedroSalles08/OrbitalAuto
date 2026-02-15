# ── OrbitalAuto · Configuração ────────────────────────────────────
"""
Carrega variáveis de ambiente do .env e expõe como constantes.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ── Orbital ───────────────────────────────────────────────────────

ORBITAL_BASE_URL: str = os.getenv("ORBITAL_BASE_URL", "https://orbital.iffarroupilha.edu.br")

# ── Sessões ───────────────────────────────────────────────────────

SESSION_EXPIRY_HOURS: int = int(os.getenv("SESSION_EXPIRY_HOURS", "4"))
MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "100"))

# ── CORS ──────────────────────────────────────────────────────────

ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]

# ── Servidor ──────────────────────────────────────────────────────

PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
