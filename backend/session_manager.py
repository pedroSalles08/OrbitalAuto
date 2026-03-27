# ── OrbitalAuto · Session Manager ─────────────────────────────────
"""
Gerenciador de sessões multi-usuário.

Mantém um dicionário em memória de sessões ativas (token → OrbitalClient).
Cada sessão expira automaticamente após SESSION_EXPIRY_HOURS de inatividade.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from orbital_client import OrbitalClient
from config import SESSION_EXPIRY_HOURS, MAX_SESSIONS

logger = logging.getLogger("session_manager")


@dataclass
class UserSession:
    """Representa uma sessão de usuário ativa."""
    token: str
    orbital: OrbitalClient
    cpf: str
    nome: str
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        """Atualiza timestamp de último uso."""
        self.last_used = datetime.now()

    def is_expired(self) -> bool:
        """Verifica se a sessão expirou por inatividade."""
        expiry = timedelta(hours=SESSION_EXPIRY_HOURS)
        return datetime.now() - self.last_used > expiry


class SessionManager:
    """
    Gerencia sessões de múltiplos usuários em memória.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, UserSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Inicia a task de limpeza periódica."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager iniciado")

    async def stop(self) -> None:
        """Para a task e encerra todas as sessões."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Logout de todas as sessões
        for session in self._sessions.values():
            try:
                session.orbital.logout()
            except Exception:
                pass

        self._sessions.clear()
        logger.info("Session manager encerrado — todas as sessões destruídas")

    # ── CRUD ─────────────────────────────────────────────────────

    def create_session(self, orbital: OrbitalClient, cpf: str, nome: str) -> str:
        """
        Cria uma nova sessão para um usuário autenticado.
        
        Args:
            orbital: Instância do OrbitalClient já autenticada.
            cpf: CPF do usuário.
            nome: Nome do usuário.
            
        Returns:
            Token da sessão (UUID).
            
        Raises:
            RuntimeError: Se o limite de sessões foi atingido.
        """
        # Verificar limite
        if len(self._sessions) >= MAX_SESSIONS:
            # Tentar limpar expiradas antes de recusar
            self._cleanup_expired()
            if len(self._sessions) >= MAX_SESSIONS:
                raise RuntimeError(
                    "Limite de sessões simultâneas atingido. "
                    "Tente novamente em alguns minutos."
                )

        # Se o mesmo CPF já tem sessão, remover a antiga
        existing = self._find_by_cpf(cpf)
        if existing:
            logger.info(f"Removendo sessão anterior para CPF {cpf[:3]}***")
            self.destroy_session(existing.token)

        token = uuid.uuid4().hex
        session = UserSession(
            token=token,
            orbital=orbital,
            cpf=cpf,
            nome=nome,
        )
        self._sessions[token] = session
        logger.info(
            f"Sessão criada para {nome} ({cpf[:3]}***) — "
            f"Total: {len(self._sessions)} sessões ativas"
        )
        return token

    def get_session(self, token: str) -> Optional[UserSession]:
        """
        Busca sessão pelo token.
        Atualiza last_used se encontrada.
        """
        session = self._sessions.get(token)
        if not session:
            return None

        if session.is_expired():
            logger.info(f"Sessão expirada para {session.nome}")
            self.destroy_session(token)
            return None

        session.touch()
        return session

    def get_session_by_cpf(self, cpf: str) -> Optional[UserSession]:
        """Busca uma sessao ativa pelo CPF."""
        existing = self._find_by_cpf(cpf)
        if not existing:
            return None
        return self.get_session(existing.token)

    def destroy_session(self, token: str) -> None:
        """Remove uma sessão e faz logout no Orbital."""
        session = self._sessions.pop(token, None)
        if session:
            try:
                session.orbital.logout()
            except Exception:
                pass
            logger.info(f"Sessão destruída para {session.nome}")

    # ── Helpers ──────────────────────────────────────────────────

    def _find_by_cpf(self, cpf: str) -> Optional[UserSession]:
        """Encontra sessão pelo CPF."""
        for session in self._sessions.values():
            if session.cpf == cpf:
                return session
        return None

    def _cleanup_expired(self) -> int:
        """Remove sessões expiradas. Retorna quantidade removida."""
        expired = [
            token for token, session in self._sessions.items()
            if session.is_expired()
        ]
        for token in expired:
            self.destroy_session(token)

        if expired:
            logger.info(f"Limpeza: {len(expired)} sessões expiradas removidas")
        return len(expired)

    async def _cleanup_loop(self) -> None:
        """Loop contínuo que limpa sessões expiradas a cada 5 minutos."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutos
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro na limpeza de sessões: {e}")

    @property
    def active_count(self) -> int:
        """Número de sessões ativas."""
        return len(self._sessions)
