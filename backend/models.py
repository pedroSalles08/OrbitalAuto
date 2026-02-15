# ── OrbitalAuto · Models ──────────────────────────────────────────
"""
Pydantic models para request/response da API.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


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
