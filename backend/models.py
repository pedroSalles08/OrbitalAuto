# ── OrbitalAuto · Models ──────────────────────────────────────────
"""
Pydantic models para request/response da API.
"""

from __future__ import annotations
from datetime import date, datetime

from pydantic import BaseModel, Field
from typing import Literal, Optional


WeekdayCode = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WeeklyRules = dict[WeekdayCode, list[str]]


# ── Auth ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    cpf: str = Field(..., description="CPF do usuário (com ou sem pontuação)")
    senha: str = Field(..., description="Senha do Orbital")


class LoginResponse(BaseModel):
    token: str
    nome: str
    message: str = "Login realizado com sucesso"


class StatusResponse(BaseModel):
    authenticated: bool
    nome: Optional[str] = None
    cpf: Optional[str] = None


# ── Refeições ────────────────────────────────────────────────────

class Refeicao(BaseModel):
    """Descrição de uma refeição em um dia do cardápio."""
    tipo: str = Field(..., description="Código: LM, AL, LT, JA")
    nome: str = Field(..., description="Nome: Lanche da Manhã, Almoço, etc.")
    descricao: Optional[str] = Field(None, description="Descrição do cardápio")


class DiaCardapio(BaseModel):
    """Cardápio de um dia inteiro."""
    data: str = Field(..., description="Data no formato YYYY-MM-DD")
    dia_semana: str = Field(..., description="Ex: Segunda-feira")
    refeicoes: list[Refeicao] = []


class CardapioResponse(BaseModel):
    semana: list[DiaCardapio] = []


# ── Agendamentos ─────────────────────────────────────────────────

class Agendamento(BaseModel):
    """Um agendamento de refeição do usuário."""
    id: int
    dia: str = Field(..., description="Data YYYY-MM-DD")
    tipo_refeicao: str = Field(..., description="Nome da refeição")
    tipo_codigo: str = Field(..., description="Código: LM, AL, LT, JA")
    confirmado: bool = False


class AgendamentosResponse(BaseModel):
    agendamentos: list[Agendamento] = []


class AgendarRequest(BaseModel):
    dia: str = Field(..., description="Data YYYY-MM-DD")
    refeicao: str = Field(..., description="Código da refeição: LM, AL, LT, JA")


class AgendarSemanaRequest(BaseModel):
    refeicoes: list[str] = Field(
        default=["LM", "AL", "LT", "JA"],
        description="Códigos das refeições a agendar"
    )


class AgendarItemRequest(BaseModel):
    dia: str = Field(..., description="Data YYYY-MM-DD")
    refeicao: str = Field(..., description="Código da refeição: LM, AL, LT, JA")


class AgendarSelecionadosRequest(BaseModel):
    """Lista específica de dia+refeição para agendar de uma vez."""
    items: list[AgendarItemRequest] = Field(
        ..., description="Lista de {dia, refeicao} para agendar"
    )


class AgendarSemanaResponse(BaseModel):
    agendados: int = 0
    erros: list[str] = []
    message: str = ""


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class AutoScheduleRunResponse(BaseModel):
    trigger: str
    enabled: bool
    dry_run: bool
    started_at: datetime
    finished_at: Optional[datetime] = None
    success: Optional[bool] = None
    message: str = ""
    used_existing_session: bool = False
    login_performed: bool = False
    candidates_count: int = 0
    scheduled_count: int = 0
    already_scheduled_count: int = 0
    skipped_count: int = 0
    errors: list[str] = Field(default_factory=list)
    last_error: Optional[str] = None


class AutoScheduleConfigRequest(BaseModel):
    enabled: bool = False
    weekly_rules: WeeklyRules = Field(default_factory=dict)
    duration_mode: str = "30d"
    orbital_password: Optional[str] = None
    clear_saved_credentials: bool = False


class AutoScheduleConfigResponse(BaseModel):
    enabled: bool
    weekly_rules: WeeklyRules = Field(default_factory=dict)
    duration_mode: str
    active_until: Optional[date] = None
    updated_at: Optional[datetime] = None
    last_successful_run_at: Optional[datetime] = None
    has_credentials: bool = False
    credentials_updated_at: Optional[datetime] = None
    primary_day: str
    primary_run_time: Optional[str] = None
    fallback_day: str
    fallback_run_time: Optional[str] = None


class AutoScheduleStatusResponse(BaseModel):
    enabled: bool
    dry_run: bool
    running: bool
    timezone: str
    weekly_rules: WeeklyRules = Field(default_factory=dict)
    duration_mode: str
    active_until: Optional[date] = None
    updated_at: Optional[datetime] = None
    last_successful_run_at: Optional[datetime] = None
    primary_day: str
    primary_run_time: Optional[str] = None
    fallback_day: str
    fallback_run_time: Optional[str] = None
    has_credentials: bool
    credentials_updated_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_run: Optional[AutoScheduleRunResponse] = None
