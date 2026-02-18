# ── OrbitalAuto · FastAPI Server ──────────────────────────────────
"""
API REST que serve como ponte entre o frontend e o sistema Orbital.

Endpoints:
  POST /api/auth/login    → Autenticar no Orbital
  POST /api/auth/logout   → Encerrar sessão
  GET  /api/auth/status   → Verificar sessão
  GET  /api/cardapio      → Cardápio da semana
  GET  /api/agendamentos  → Agendamentos do usuário
  POST /api/agendar       → Agendar uma refeição
  POST /api/agendar-semana→ Agendar todas as refeições da semana
  DELETE /api/agendar/{id}→ Cancelar um agendamento
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import ALLOWED_ORIGINS, PORT, DEBUG, DESKTOP_MODE
from models import (
    LoginRequest, LoginResponse, StatusResponse,
    CardapioResponse, DiaCardapio, Refeicao,
    AgendamentosResponse, Agendamento,
    AgendarRequest, AgendarSemanaRequest, AgendarSemanaResponse,
    AgendarSelecionadosRequest,
    MessageResponse,
)
from orbital_client import (
    OrbitalClient, OrbitalError, OrbitalLoginError, OrbitalSessionExpired,
    MEAL_CODES,
)
from session_manager import SessionManager, UserSession


# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app")


# ── Session Manager (global) ─────────────────────────────────────

session_manager = SessionManager()


# ── Lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown do servidor."""
    await session_manager.start()
    logger.info("🚀 OrbitalAuto backend iniciado")
    yield
    await session_manager.stop()
    logger.info("OrbitalAuto backend encerrado")


# ── App ──────────────────────────────────────────────────────────

app = FastAPI(
    title="OrbitalAuto API",
    description="Automação de agendamento de refeições do Orbital IFFarroupilha",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency: Extrair sessão do token ──────────────────────────

async def get_current_session(request: Request) -> UserSession:
    """
    Extrai e valida o token de sessão do header Authorization.
    Usado como dependency em rotas protegidas.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token não fornecido")

    token = auth_header[7:]  # Remove "Bearer "

    session = session_manager.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida")

    return session


# ── Helpers ──────────────────────────────────────────────────────

def _pode_agendar(dia: str) -> tuple[bool, str]:
    """
    Verifica se o agendamento é permitido para a data.
    Regra: até 17h do dia anterior à refeição.
    
    Returns:
        (pode, motivo)
    """
    try:
        data_refeicao = datetime.strptime(dia, "%Y-%m-%d").date()
    except ValueError:
        return False, "Data inválida"

    agora = datetime.now()
    hoje = agora.date()

    # Data já passou
    if data_refeicao < hoje:
        return False, "Data já passou"

    # Se é para hoje, verificar se já passou das 17h de ontem
    # (i.e., nunca se pode agendar para o mesmo dia no dia)
    if data_refeicao == hoje:
        return False, "Não é possível agendar para hoje (prazo: até 17h de ontem)"

    # Se é para amanhã, verificar se passou das 17h de hoje
    if data_refeicao == hoje + timedelta(days=1):
        if agora.hour >= 17:
            return False, "Prazo expirado (agendamento até 17h do dia anterior)"

    return True, "OK"


def _pode_desagendar(dia: str) -> tuple[bool, str]:
    """
    Verifica se o desagendamento é permitido.
    Regra: até 9h do dia da refeição.
    
    Returns:
        (pode, motivo)
    """
    try:
        data_refeicao = datetime.strptime(dia, "%Y-%m-%d").date()
    except ValueError:
        return False, "Data inválida"

    agora = datetime.now()
    hoje = agora.date()

    if data_refeicao < hoje:
        return False, "Data já passou"

    if data_refeicao == hoje and agora.hour >= 9:
        return False, "Prazo expirado (desagendamento até 9h do dia da refeição)"

    return True, "OK"


# ══════════════════════════════════════════════════════════════════
# ROTAS
# ══════════════════════════════════════════════════════════════════


# ── Auth ─────────────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    """Autentica o usuário no Orbital e cria uma sessão."""
    cpf = re.sub(r"\D", "", payload.cpf)

    if len(cpf) != 11:
        raise HTTPException(status_code=400, detail="CPF inválido — deve ter 11 dígitos")

    client = OrbitalClient()

    try:
        nome = client.login(cpf, payload.senha)
    except OrbitalLoginError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except OrbitalError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Erro inesperado no login")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

    try:
        token = session_manager.create_session(client, cpf, nome)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return LoginResponse(token=token, nome=nome)


@app.post("/api/auth/logout", response_model=MessageResponse)
async def logout(session: UserSession = Depends(get_current_session)):
    """Encerra a sessão do usuário."""
    session_manager.destroy_session(session.token)
    return MessageResponse(message="Logout realizado com sucesso")


@app.get("/api/auth/status", response_model=StatusResponse)
async def auth_status(request: Request):
    """Verifica se o token ainda é válido."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return StatusResponse(authenticated=False)

    token = auth_header[7:]
    session = session_manager.get_session(token)

    if not session:
        return StatusResponse(authenticated=False)

    return StatusResponse(
        authenticated=True,
        nome=session.nome,
        cpf=session.cpf[:3] + "***",
    )


# ── Cardápio ─────────────────────────────────────────────────────

@app.get("/api/cardapio", response_model=CardapioResponse)
async def get_cardapio(session: UserSession = Depends(get_current_session)):
    """Retorna o cardápio da semana."""
    try:
        raw = session.orbital.get_cardapio()
    except OrbitalSessionExpired:
        logger.warning("Sessão Orbital expirada ao buscar cardápio")
        raise HTTPException(status_code=502, detail="Sessão expirada no Orbital. Tente fazer logout e login novamente.")
    except OrbitalError as e:
        raise HTTPException(status_code=502, detail=str(e))

    semana = []
    for dia in raw:
        refeicoes = [
            Refeicao(tipo=r["tipo"], nome=r["nome"], descricao=r.get("descricao"))
            for r in dia.get("refeicoes", [])
        ]
        semana.append(DiaCardapio(
            data=dia["data"],
            dia_semana=dia.get("dia_semana", ""),
            refeicoes=refeicoes,
        ))

    return CardapioResponse(semana=semana)


# ── Agendamentos ─────────────────────────────────────────────────

@app.get("/api/agendamentos", response_model=AgendamentosResponse)
async def get_agendamentos(session: UserSession = Depends(get_current_session)):
    """Lista os agendamentos do usuário."""
    try:
        raw = session.orbital.get_agendamentos()
    except OrbitalSessionExpired:
        logger.warning("Sessão Orbital expirada ao buscar agendamentos")
        raise HTTPException(status_code=502, detail="Sessão expirada no Orbital. Tente fazer logout e login novamente.")
    except OrbitalError as e:
        raise HTTPException(status_code=502, detail=str(e))

    agendamentos = [
        Agendamento(
            id=a["id"],
            dia=a["dia"],
            tipo_refeicao=a["tipo_refeicao"],
            tipo_codigo=a["tipo_codigo"],
            confirmado=a.get("confirmado", False),
        )
        for a in raw
    ]

    return AgendamentosResponse(agendamentos=agendamentos)


# ── Agendar ──────────────────────────────────────────────────────

@app.post("/api/agendar", response_model=MessageResponse)
async def agendar(
    payload: AgendarRequest,
    session: UserSession = Depends(get_current_session),
):
    """Agenda uma refeição para um dia específico."""
    # Validar código da refeição
    if payload.refeicao not in MEAL_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Refeição inválida: {payload.refeicao}. Use: {', '.join(MEAL_CODES.keys())}",
        )

    # Verificar prazo
    pode, motivo = _pode_agendar(payload.dia)
    if not pode:
        raise HTTPException(status_code=400, detail=motivo)

    try:
        session.orbital.agendar(payload.dia, payload.refeicao)
    except OrbitalSessionExpired:
        logger.warning(f"Sessão Orbital expirada ao agendar (token={session.token[:8]}...)")
        raise HTTPException(status_code=502, detail="Sessão expirada no Orbital. Faça login novamente.")
    except OrbitalError as e:
        raise HTTPException(status_code=400, detail=str(e))

    nome_refeicao = MEAL_CODES[payload.refeicao]["nome"]
    return MessageResponse(
        message=f"{nome_refeicao} agendado para {payload.dia}",
        success=True,
    )


@app.post("/api/agendar-semana", response_model=AgendarSemanaResponse)
async def agendar_semana(
    payload: AgendarSemanaRequest = AgendarSemanaRequest(),
    session: UserSession = Depends(get_current_session),
):
    """Agenda todas as refeições selecionadas para todos os dias disponíveis da semana."""
    # Buscar cardápio para saber quais dias existem
    try:
        cardapio = session.orbital.get_cardapio()
    except OrbitalSessionExpired:
        logger.warning(f"Sessão Orbital expirada ao buscar cardápio para semana (token={session.token[:8]}...)")
        raise HTTPException(status_code=502, detail="Sessão expirada no Orbital. Faça login novamente.")
    except OrbitalError as e:
        raise HTTPException(status_code=502, detail=str(e))

    agendados = 0
    erros: list[str] = []

    for dia in cardapio:
        data = dia["data"]
        pode, motivo = _pode_agendar(data)
        if not pode:
            continue  # Pulardays que não podem ser agendados

        for codigo in payload.refeicoes:
            if codigo not in MEAL_CODES:
                continue

            try:
                session.orbital.agendar(data, codigo)
                agendados += 1
            except OrbitalError as e:
                nome = MEAL_CODES[codigo]["nome"]
                erros.append(f"{data} - {nome}: {e}")

    msg = f"{agendados} refeição(ões) agendada(s)"
    if erros:
        msg += f" ({len(erros)} erro(s))"

    return AgendarSemanaResponse(
        agendados=agendados,
        erros=erros,
        message=msg,
    )


# ── Agendar Selecionados ─────────────────────────────────────────

@app.post("/api/agendar-selecionados", response_model=AgendarSemanaResponse)
async def agendar_selecionados(
    payload: AgendarSelecionadosRequest,
    session: UserSession = Depends(get_current_session),
):
    """
    Agenda uma lista específica de pares dia+refeição.
    Diferente de /agendar-semana, aceita seleção granular do usuário.
    """
    agendados = 0
    erros: list[str] = []

    for item in payload.items:
        # Validar código
        if item.refeicao not in MEAL_CODES:
            erros.append(f"{item.dia} - Refeição inválida: {item.refeicao}")
            continue

        # Verificar prazo
        pode, motivo = _pode_agendar(item.dia)
        if not pode:
            nome = MEAL_CODES[item.refeicao]["nome"]
            erros.append(f"{item.dia} - {nome}: {motivo}")
            continue

        try:
            session.orbital.agendar(item.dia, item.refeicao)
            agendados += 1
        except OrbitalSessionExpired:
            logger.warning(f"Sessão Orbital expirada ao agendar selecionados")
            raise HTTPException(
                status_code=502,
                detail="Sessão expirada no Orbital. Faça login novamente.",
            )
        except OrbitalError as e:
            nome = MEAL_CODES[item.refeicao]["nome"]
            erros.append(f"{item.dia} - {nome}: {e}")

    msg = f"{agendados} refeição(ões) agendada(s)"
    if erros:
        msg += f" ({len(erros)} erro(s))"

    return AgendarSemanaResponse(agendados=agendados, erros=erros, message=msg)


# ── Desagendar ───────────────────────────────────────────────────

@app.delete("/api/agendar/{agendamento_id}", response_model=MessageResponse)
async def desagendar(
    agendamento_id: int,
    dia: str = "",
    session: UserSession = Depends(get_current_session),
):
    """
    Cancela um agendamento pelo ID.
    
    Query param 'dia' (YYYY-MM-DD) é opcional — usado para validar o prazo.
    """
    # Se temos a data, validar prazo de desagendamento
    if dia:
        pode, motivo = _pode_desagendar(dia)
        if not pode:
            raise HTTPException(status_code=400, detail=motivo)

    try:
        session.orbital.desagendar(agendamento_id)
    except OrbitalSessionExpired:
        logger.warning(f"Sessão Orbital expirada ao desagendar (token={session.token[:8]}...)")
        raise HTTPException(status_code=502, detail="Sessão expirada no Orbital. Faça login novamente.")
    except OrbitalError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return MessageResponse(message="Agendamento cancelado com sucesso", success=True)


# ── Health Check ─────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check do servidor."""
    return {
        "status": "ok",
        "sessoes_ativas": session_manager.active_count,
        "timestamp": datetime.now().isoformat(),
    }


# ── Debug ─────────────────────────────────────────────────────────

def _get_debug_session(request: Request, token: str | None = None) -> UserSession:
    """Helper para debug endpoints — aceita token via header OU query param."""
    # Tentar query param primeiro (mais fácil de usar no browser)
    if token:
        session = session_manager.get_session(token)
        if session:
            return session

    # Fallback: header Authorization
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        t = auth_header[7:]
        session = session_manager.get_session(t)
        if session:
            return session

    raise HTTPException(status_code=401, detail="Token não fornecido. Use ?token=SEU_TOKEN na URL")


@app.get("/api/debug")
async def debug_info(request: Request, token: str | None = None):
    """Endpoint de diagnóstico — testa endpoints do Orbital e retorna info da sessão."""
    session = _get_debug_session(request, token)

    debug = session.orbital.get_debug_info()
    api_tests = session.orbital.debug_test_api()

    return {
        "login_debug": debug,
        "api_tests": api_tests,
        "session_token": session.token[:8] + "...",
        "session_created": session.created_at.isoformat(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/debug/start-page")
async def debug_start_page(request: Request, token: str | None = None):
    """Retorna o HTML bruto da página /start para diagnóstico."""
    session = _get_debug_session(request, token)
    html = session.orbital.fetch_start_page_html()
    parsed = session.orbital.parse_start_page(html)
    return {"parsed": parsed, "html_length": len(html)}


@app.get("/api/debug/vinculos")
async def debug_vinculos(request: Request, token: str | None = None):
    """Testa as APIs de vínculo (get-user-logged e set-user)."""
    session = _get_debug_session(request, token)
    result = session.orbital.debug_vinculos()
    return result


@app.get("/api/debug/routes")
async def debug_routes(request: Request, token: str | None = None):
    """Mostra as rotas Ziggy com seus URIs reais — foco em refeitório."""
    session = _get_debug_session(request, token)
    all_routes = session.orbital._extract_ziggy_routes()
    # Filtrar rotas relevantes
    refeitorio = {k: v for k, v in all_routes.items() if "refeitorio" in k.lower()}
    agendamento = {k: v for k, v in all_routes.items() if "agendamento" in k.lower()}
    refeicao = {k: v for k, v in all_routes.items() if "refeicao" in k.lower() or "refeicoe" in k.lower()}
    return {
        "refeitorio_routes": refeitorio,
        "agendamento_routes": agendamento,
        "refeicao_routes": refeicao,
        "total_routes": len(all_routes),
    }


# ── Static Files (Desktop Mode) ──────────────────────────────────

if DESKTOP_MODE:
    # Resolve the path to the static frontend build
    _base_dir = Path(getattr(
        __import__("sys"), "_MEIPASS", Path(__file__).resolve().parent
    ))
    _static_dir = _base_dir / "out"

    if _static_dir.is_dir():
        # Mount Next.js static assets (_next/static, etc.)
        _next_dir = _static_dir / "_next"
        if _next_dir.is_dir():
            app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="next_static")

        # Serve other static files (favicon, images, etc.)
        @app.get("/favicon.ico")
        async def favicon():
            fav = _static_dir / "favicon.ico"
            if fav.exists():
                return FileResponse(str(fav))
            raise HTTPException(404)

        # SPA catch-all: serve the correct HTML for known routes
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Try exact .html file first (Next.js static export creates /login.html, /dashboard.html)
            html_file = _static_dir / f"{full_path}.html"
            if html_file.is_file():
                return FileResponse(str(html_file))

            # Try directory index
            index_file = _static_dir / full_path / "index.html"
            if index_file.is_file():
                return FileResponse(str(index_file))

            # Try exact file (for any other static assets)
            exact_file = _static_dir / full_path
            if exact_file.is_file():
                return FileResponse(str(exact_file))

            # Fallback to root index.html (SPA routing)
            root_index = _static_dir / "index.html"
            if root_index.is_file():
                return FileResponse(str(root_index))

            raise HTTPException(404, detail="Página não encontrada")

        logger.info(f"📂 Desktop mode: serving static files from {_static_dir}")
    else:
        logger.warning(f"⚠️  Desktop mode ON but no 'out' directory found at {_static_dir}")


# ── Run ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=DEBUG)
