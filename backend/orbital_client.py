# ── OrbitalAuto · Orbital Client ──────────────────────────────────
"""
Cliente HTTP que automatiza a interação com o sistema Orbital do IFFarroupilha.

Fluxo:
  1. GET /login → obtém XSRF-TOKEN dos cookies
  2. POST /login com CPF + senha (sem follow redirect)
  3. Seguir redirect manualmente para /start (página autenticada)
  4. Usar rotas manuais (mapeadas do JS bundle) para chamar endpoints
  5. Busca nome do usuário, cardápio e gerencia agendamentos
"""

from __future__ import annotations

import json
import re
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from config import ORBITAL_BASE_URL

logger = logging.getLogger("orbital_client")

# ── Mapeamento de refeições ──────────────────────────────────────

MEAL_CODES = {
    "LM": {"field": "lanche_da_manha", "nome": "Lanche da Manhã"},
    "AL": {"field": "almoco", "nome": "Almoço"},
    "LT": {"field": "lanche_da_tarde", "nome": "Lanche da Tarde"},
    "JA": {"field": "jantar", "nome": "Jantar"},
}

ALL_MEAL_FIELDS = [
    "cafe_da_manha", "lanche_da_manha", "almoco",
    "lanche_da_tarde", "jantar", "lanche_da_noite",
]

DIAS_SEMANA = [
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado", "Domingo",
]

# ── Mapeamento manual das rotas ──────────────────────────────────
# Extraído da análise do main.js bundle do Orbital.
# O Orbital usa Ziggy (Laravel → JS), mas as rotas são compiladas
# no main.js, não inline no HTML. Então usamos mapeamento fixo.

ORBITAL_ROUTES = {
    # Auth & user selection
    "get.user.logged": "get-logged-user",
    "set.user": "set-user",
    # Refeitório — Refeição (cardápio)
    "refeitorio.refeicao.index": "refeitorio/refeicao",
    "api.refeitorio.refeicao.refeicoes": "refeitorio/refeicao/api/get-refeicoes",
    "refeitorio.refeicao.get": "refeitorio/refeicao/get/{id}",
    # Refeitório — Agendamento
    "refeitorio.agendamento.index": "refeitorio/agendamento",
    "refeitorio.agendamento.store": "refeitorio/agendamento/store",
    "refeitorio.agendamento.destroy": "refeitorio/agendamento/delete/{id}",
    "api.refeitorio.agendamento.agendamentos": "refeitorio/agendamento/get-agendamentos",
    "refeitorio.agendamento.review": "refeitorio/agendamento/review/{id_refeicao}",
    "refeitorio.agendamento.verify.schedule": "refeitorio/agendamento/api/verify-dates",
    # Outros
    "api.get.unidades": "api/get-unidades",
    "dashboard": "dashboard",
}


# ── Exceções ─────────────────────────────────────────────────────

class OrbitalError(Exception):
    """Erro genérico do Orbital."""
    pass


class OrbitalLoginError(OrbitalError):
    """Falha no login (CPF/senha inválidos)."""
    pass


class OrbitalSessionExpired(OrbitalError):
    """Sessão expirada no Orbital."""
    pass


# ── Client ───────────────────────────────────────────────────────

class OrbitalClient:
    """
    Gerencia uma sessão autenticada com o Orbital.
    Cada instância representa um usuário logado.
    """

    def __init__(self) -> None:
        self.base_url: str = ORBITAL_BASE_URL.rstrip("/")
        self.session: requests.Session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self.nome_usuario: str = ""
        self.cpf: str = ""
        self._authenticated: bool = False
        self._vinculos: list[dict] = []
        # Diagnóstico — armazena informações para debug
        self._debug_info: dict[str, Any] = {}

    # ── Helpers ──────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        """Constrói URL absoluta."""
        return f"{self.base_url}/{path.lstrip('/')}"

    def _get_xsrf_token(self) -> str:
        """Extrai o XSRF-TOKEN dos cookies da sessão."""
        token = self.session.cookies.get("XSRF-TOKEN", "")
        # Laravel URL-encoda o token; precisamos decodificar
        return requests.utils.unquote(token)

    def _route_url(self, name: str, params: dict | None = None) -> str:
        """Resolve uma rota nomeada para URL completa."""
        uri = ORBITAL_ROUTES.get(name)
        if not uri:
            raise OrbitalError(f"Rota desconhecida: {name}")
        if params:
            for key, value in params.items():
                uri = uri.replace(f"{{{key}}}", str(value))
        return self._url(uri)

    def _ensure_authenticated(self) -> None:
        """Verifica se a sessão está autenticada."""
        if not self._authenticated:
            raise OrbitalSessionExpired("Sessão não autenticada")

    def _api_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Faz uma requisição autenticada com CSRF e headers de AJAX.
        Não segue redirects automaticamente para detectar sessão expirada.
        """
        headers = kwargs.pop("headers", {})
        headers["X-XSRF-TOKEN"] = self._get_xsrf_token()
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Accept"] = "application/json"
        headers["Referer"] = self._url("/start")

        try:
            resp = self.session.request(
                method, url,
                headers=headers,
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException as e:
            logger.error(f"Erro de rede: {e}")
            raise OrbitalError(f"Erro de conexão com o Orbital: {e}")

        # Detectar sessão expirada
        if resp.status_code in (401, 419):
            self._authenticated = False
            raise OrbitalSessionExpired("Sessão expirada no Orbital (401/419)")

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location", "")
            if "/login" in location:
                self._authenticated = False
                raise OrbitalSessionExpired("Sessão expirada no Orbital (redirect para login)")
            # Se redirect não é para login, seguir manualmente
            logger.debug(f"Redirect {resp.status_code} → {location}")
            full_url = location if location.startswith("http") else self._url(location)
            return self.session.get(full_url, headers=headers, allow_redirects=True)

        return resp

    # ── Login ────────────────────────────────────────────────────

    def login(self, cpf: str, senha: str) -> str:
        """
        Autentica no Orbital.

        Returns:
            Nome do usuário logado.

        Raises:
            OrbitalLoginError: Se CPF/senha incorretos.
            OrbitalError: Se ocorrer erro de rede.
        """
        cpf_limpo = re.sub(r"\D", "", cpf)
        self.cpf = cpf_limpo
        debug: dict[str, Any] = {}

        logger.info(f"Iniciando login para CPF: {cpf_limpo[:3]}***")

        # ─── Passo 1: GET /login → cookies XSRF + _token do form ─
        try:
            resp = self.session.get(self._url("/login"), allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise OrbitalError(f"Não foi possível acessar o Orbital: {e}")

        debug["step1_status"] = resp.status_code
        debug["step1_url"] = resp.url
        debug["step1_cookies"] = list(self.session.cookies.keys())

        # Extrair _token do formulário HTML
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_input = soup.find("input", {"name": "_token"})
        csrf_token = csrf_input["value"] if csrf_input else ""
        debug["step1_csrf_found"] = bool(csrf_token)

        if not csrf_token:
            logger.warning("_token não encontrado no formulário de login")

        # ─── Passo 2: POST /login (sem follow redirect) ──────────
        login_data = {
            "_token": csrf_token,
            "login": cpf_limpo,
            "senha": senha,
        }

        try:
            resp = self.session.post(
                self._url("/login"),
                data=login_data,
                headers={
                    "X-XSRF-TOKEN": self._get_xsrf_token(),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": self._url("/login"),
                    "Origin": self.base_url,
                },
                allow_redirects=False,
            )
        except requests.RequestException as e:
            raise OrbitalError(f"Erro ao fazer login: {e}")

        debug["step2_status"] = resp.status_code
        debug["step2_location"] = resp.headers.get("Location", "")
        debug["step2_cookies"] = list(self.session.cookies.keys())

        # ─── Passo 3: Verificar resultado ─────────────────────────
        if resp.status_code == 200:
            # 200 na mesma URL = ficou na página de login = credenciais erradas
            error_soup = BeautifulSoup(resp.text, "html.parser")
            error_div = (
                error_soup.find("div", class_="alert-danger")
                or error_soup.find("div", class_="invalid-feedback")
            )
            error_msg = (
                error_div.get_text(strip=True) if error_div else "CPF ou senha inválidos"
            )
            self._debug_info = debug
            raise OrbitalLoginError(error_msg)

        if resp.status_code in (301, 302, 303):
            location = resp.headers.get("Location", "")
            debug["step2_redirect_to"] = location

            # Redirect para /login = falhou — seguir redirect para pegar mensagem de erro
            if "/login" in location:
                full_url = location if location.startswith("http") else self._url(location)
                error_resp = self.session.get(full_url, allow_redirects=True)
                error_soup = BeautifulSoup(error_resp.text, "html.parser")
                error_div = (
                    error_soup.find("div", class_="alert-danger")
                    or error_soup.find("div", class_="alert")
                    or error_soup.find("div", class_="invalid-feedback")
                )
                if error_div:
                    # Limpar o texto (remover "×" de botão de fechar)
                    error_msg = error_div.get_text(strip=True).lstrip("×").strip()
                else:
                    error_msg = "CPF ou senha inválidos"
                debug["error_msg_from_page"] = error_msg
                self._debug_info = debug
                raise OrbitalLoginError(error_msg)

            # Sucesso! Seguir o redirect para a página autenticada
            logger.info(f"Login redirect → {location}")
            full_url = location if location.startswith("http") else self._url(location)

            resp = self.session.get(full_url, allow_redirects=True)
            debug["step3_status"] = resp.status_code
            debug["step3_final_url"] = resp.url
            debug["step3_cookies"] = list(self.session.cookies.keys())
            debug["step3_html_length"] = len(resp.text)
        else:
            # Status inesperado
            debug["step2_note"] = f"Status inesperado: {resp.status_code}"
            logger.warning(f"Login retornou status inesperado: {resp.status_code}")

        # ─── Passo 4: Marcar como autenticado (parcial — falta selecionar vínculo)
        self._authenticated = True

        # ─── Passo 5: Buscar info do usuário + vínculos via POST /get-logged-user
        user_info = self._get_logged_user()
        debug["step5_user_info"] = str(user_info)[:500]

        if user_info and not user_info.get("error"):
            response = user_info.get("response", {})
            user = response.get("user", {})
            self.nome_usuario = user.get("name", "")
            # vínculos ficam dentro de response.types (não no nível raiz)
            self._vinculos = response.get("types", [])
            debug["vinculos_count"] = len(self._vinculos)
        else:
            # Fallback: tentar extrair do HTML
            self._extract_user_name_from_html(resp.text)
            self._vinculos = []

        # ─── Passo 6: Selecionar primeiro vínculo automaticamente ─
        if self._vinculos:
            vinculo = self._vinculos[0]  # Primeiro vínculo (geralmente só tem 1)
            vinculo_id = vinculo.get("identity")
            vinculo_detail = vinculo.get("detail", "")
            logger.info(f"Selecionando vínculo: {vinculo_detail} (id={vinculo_id})")

            set_ok = self._set_user(vinculo_id)
            debug["step6_set_user"] = set_ok
            debug["step6_vinculo"] = vinculo_detail

            if not set_ok:
                logger.warning("Falha ao selecionar vínculo — sessão pode não funcionar")
        else:
            logger.warning("Nenhum vínculo encontrado — pulando seleção de curso")
            debug["step6_note"] = "Sem vínculos"

        # Fallback para nome
        if not self.nome_usuario:
            self.nome_usuario = f"Usuário ({self.cpf[:3]}***)"

        debug["user_name"] = self.nome_usuario
        debug["authenticated"] = True
        self._debug_info = debug

        logger.info(f"Login bem-sucedido: {self.nome_usuario}")
        logger.debug(f"Debug info: {json.dumps(debug, indent=2, ensure_ascii=False)}")

        return self.nome_usuario

    # ── Seleção de vínculo/curso ─────────────────────────────────

    def _get_logged_user(self) -> dict[str, Any]:
        """
        POST /get-logged-user → retorna info do usuário e vínculos.
        
        Resposta esperada:
        {
            "error": false,
            "message": "Dados carregador com sucesso.",
            "response": {"user": {"name": "...", "email": "..."}},
            "types": [{"identity": 2024317756, "detail": "Curso: Técnico Em Informática"}]
        }
        """
        try:
            url = self._route_url("get.user.logged")
            resp = self._api_request("POST", url)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"get-logged-user retornou {resp.status_code}: {resp.text[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Erro ao buscar get-logged-user: {e}")
            return {}

    def _set_user(self, identity: int) -> bool:
        """
        POST /set-user → seleciona o vínculo ativo (curso/matrícula).
        Depois GET /dashboard para finalizar a ativação da sessão.
        
        Args:
            identity: ID do vínculo (obtido de _get_logged_user)
        
        Returns:
            True se sucesso
        """
        try:
            url = self._route_url("set.user")
            resp = self._api_request("POST", url, json={"slc_link": identity})
            logger.info(f"set-user response: status={resp.status_code}")
            success = False
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    logger.info(f"set-user data: {str(data)[:300]}")
                    success = not data.get("error", True)
                except ValueError:
                    success = True
            
            # Passo crucial: visitar /dashboard para completar a sessão.
            # O Orbital precisa deste acesso para ativar o contexto.
            logger.info("Visitando /dashboard para completar sessão...")
            try:
                dash_resp = self.session.get(
                    self._url("/dashboard"),
                    headers={
                        "Accept": "text/html",
                        "Referer": self._url("/start"),
                    },
                    allow_redirects=True,
                )
                logger.info(f"Dashboard visit: status={dash_resp.status_code}, url={dash_resp.url}")
                self._debug_info["dashboard_visit"] = {
                    "status": dash_resp.status_code,
                    "url": dash_resp.url,
                    "redirected_to_login": "/login" in dash_resp.url,
                }
            except Exception as e:
                logger.warning(f"Falha ao visitar /dashboard: {e}")

            # Passo 2: visitar a página do refeitório para ativar o contexto
            # do módulo. Laravel pode usar middleware que exige essa navegação.
            logger.info("Visitando /refeitorio/refeicao para ativar contexto do refeitório...")
            try:
                ref_resp = self.session.get(
                    self._url("/refeitorio/refeicao"),
                    headers={
                        "Accept": "text/html",
                        "Referer": self._url("/dashboard"),
                    },
                    allow_redirects=True,
                )
                logger.info(f"Refeitório visit: status={ref_resp.status_code}, url={ref_resp.url}")
                self._debug_info["refeitorio_visit"] = {
                    "status": ref_resp.status_code,
                    "url": ref_resp.url,
                    "redirected_to_login": "/login" in ref_resp.url,
                }
            except Exception as e:
                logger.warning(f"Falha ao visitar /refeitorio/refeicao: {e}")

            return success
        except Exception as e:
            logger.error(f"Erro ao selecionar vínculo: {e}")
            return False

    def get_vinculos(self) -> list[dict]:
        """Retorna a lista de vínculos do usuário (obtida durante login)."""
        return self._vinculos

    # ── Extração de nome ─────────────────────────────────────────

    def _extract_user_name_from_html(self, html: str) -> None:
        """
        Tenta extrair o nome do usuário do HTML.
        O /start é um shell Vue SPA — o nome normalmente não está no HTML.
        Mas tentamos por completude.
        """
        # Tentar em elementos HTML
        soup = BeautifulSoup(html, "html.parser")
        for selector in [
            {"class_": "user-name"},
            {"class_": "username"},
            {"class_": "nome-usuario"},
            {"id": "user-name"},
        ]:
            el = soup.find(attrs=selector)
            if el and el.get_text(strip=True):
                self.nome_usuario = el.get_text(strip=True)
                logger.info(f"Nome encontrado no HTML: {self.nome_usuario}")
                return

        # Tentar em scripts inline (props do Vue, Pinia, etc.)
        for pattern in [
            r'"nome"\s*:\s*"([^"]{2,})"',
            r'"name"\s*:\s*"([^"]{2,})"',
            r'"user_name"\s*:\s*"([^"]{2,})"',
            r'"nomeCompleto"\s*:\s*"([^"]{2,})"',
        ]:
            match = re.search(pattern, html)
            if match:
                name = match.group(1)
                # Evitar pegar nomes genéricos de configuração
                if len(name) > 3 and name.lower() not in ("routes", "locale", "app.js", "main.js"):
                    self.nome_usuario = name
                    logger.info(f"Nome encontrado em script: {self.nome_usuario}")
                    return

        # Fallback — será sobrescrito por _fetch_user_name se possível
        self.nome_usuario = f"Usuário ({self.cpf[:3]}***)"

    def _fetch_user_name(self) -> None:
        """
        Tenta buscar o nome do usuário via chamadas API internas do Orbital.
        """
        # Tentativa 1: Buscar agendamentos — a resposta pode conter info do usuário
        try:
            url = self._route_url("api.refeitorio.agendamento.agendamentos")
            resp = self._api_request("GET", url, params={"page": 1, "offset": 1})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    # Alguns endpoints Laravel retornam user info no wrapper
                    user = data.get("user") or data.get("usuario")
                    if isinstance(user, dict):
                        name = user.get("nome") or user.get("name", "")
                        if name:
                            self.nome_usuario = name
                            logger.info(f"Nome via agendamentos API: {self.nome_usuario}")
                            return
        except Exception as e:
            logger.debug(f"Falha ao buscar nome via agendamentos: {e}")

        # Tentativa 2: GET /start e parsear o HTML completo da SPA
        try:
            resp = self.session.get(
                self._url("/start"),
                headers={
                    "Accept": "text/html",
                    "X-XSRF-TOKEN": self._get_xsrf_token(),
                },
                allow_redirects=True,
            )
            if resp.status_code == 200 and "/login" not in resp.url:
                for pattern in [
                    r'"nome"\s*:\s*"([^"]{2,})"',
                    r'"name"\s*:\s*"([^"]{2,})"',
                    r'"user"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"',
                ]:
                    match = re.search(pattern, resp.text)
                    if match:
                        name = match.group(1)
                        if len(name) > 3 and name.lower() not in ("routes", "locale"):
                            self.nome_usuario = name
                            logger.info(f"Nome via /start HTML: {self.nome_usuario}")
                            return
        except Exception as e:
            logger.debug(f"Falha ao buscar nome via /start: {e}")

        logger.warning("Não foi possível encontrar o nome do usuário, usando fallback")

    # ── Diagnóstico ──────────────────────────────────────────────

    def fetch_start_page_html(self) -> str:
        """Busca e retorna o HTML bruto da página /start (para diagnóstico)."""
        self._ensure_authenticated()
        try:
            resp = self.session.get(
                self._url("/start"),
                headers={"Accept": "text/html"},
                allow_redirects=True,
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    def parse_start_page(self, html: str) -> dict[str, Any]:
        """
        Parseia o HTML da página /start e extrai informações relevantes:
        - Forms, inputs, buttons
        - Texto visível (nome do user, cursos/matrículas)
        - Links
        """
        soup = BeautifulSoup(html, "html.parser")
        result: dict[str, Any] = {}

        # Extrair título
        title = soup.find("title")
        result["title"] = title.get_text(strip=True) if title else ""

        # Extrair forms
        forms = []
        for form in soup.find_all("form"):
            form_data: dict[str, Any] = {
                "action": form.get("action", ""),
                "method": form.get("method", ""),
                "id": form.get("id", ""),
                "class": form.get("class", []),
                "inputs": [],
            }
            for inp in form.find_all(["input", "select", "textarea"]):
                inp_data = {
                    "tag": inp.name,
                    "name": inp.get("name", ""),
                    "type": inp.get("type", ""),
                    "value": (inp.get("value", "") or "")[:100],
                    "id": inp.get("id", ""),
                }
                if inp.name == "select":
                    options = []
                    for opt in inp.find_all("option"):
                        options.append({
                            "value": opt.get("value", ""),
                            "text": opt.get_text(strip=True),
                            "selected": opt.has_attr("selected"),
                        })
                    inp_data["options"] = options
                form_data["inputs"].append(inp_data)
            forms.append(form_data)
        result["forms"] = forms

        # Extrair botões e links com texto significativo
        buttons = []
        for btn in soup.find_all(["button", "a"]):
            text = btn.get_text(strip=True)
            if text and len(text) > 1:
                buttons.append({
                    "tag": btn.name,
                    "text": text[:100],
                    "href": btn.get("href", ""),
                    "onclick": btn.get("onclick", "")[:200],
                    "type": btn.get("type", ""),
                    "class": btn.get("class", []),
                })
        result["buttons_links"] = buttons[:30]  # limitar

        # Extrair texto visível do body (sem scripts/styles)
        body = soup.find("body")
        if body:
            for tag in body.find_all(["script", "style", "link"]):
                tag.decompose()
            text_parts = [t.strip() for t in body.stripped_strings if len(t.strip()) > 2]
            result["visible_text"] = text_parts[:50]

        # Extrair cards ou divs com classes específicas (matrícula, curso, vínculo)
        cards = []
        for div in soup.find_all("div", class_=True):
            classes = " ".join(div.get("class", []))
            if any(kw in classes.lower() for kw in ["card", "panel", "vinculo", "matricula", "curso"]):
                text = div.get_text(strip=True)[:300]
                if text:
                    cards.append({"classes": classes, "text": text})
        result["relevant_cards"] = cards[:10]

        # Extrair Ziggy routes se presentes
        for script in soup.find_all("script"):
            text = script.string or ""
            if "Ziggy" in text:
                # Extrair o JSON de Ziggy
                m = re.search(r'const\s+Ziggy\s*=\s*(\{.*?\});', text, re.DOTALL)
                if m:
                    try:
                        ziggy = json.loads(m.group(1))
                        result["ziggy_url"] = ziggy.get("url", "")
                        # Só os nomes das rotas
                        result["ziggy_route_names"] = list(ziggy.get("routes", {}).keys())
                    except json.JSONDecodeError:
                        result["ziggy_parse_error"] = True

        return result

    def _extract_ziggy_routes(self) -> dict[str, dict]:
        """
        Busca o HTML de /start e extrai as rotas Ziggy (nome → {uri, methods}).
        """
        try:
            resp = self.session.get(
                self._url("/start"),
                headers={"Accept": "text/html"},
                allow_redirects=True,
            )
            m = re.search(r'const\s+Ziggy\s*=\s*(\{.*?\})\s*;', resp.text, re.DOTALL)
            if m:
                ziggy = json.loads(m.group(1))
                return ziggy.get("routes", {})
        except Exception as e:
            logger.error(f"Erro ao extrair rotas Ziggy: {e}")
        return {}

    def debug_vinculos(self) -> dict[str, Any]:
        """
        1) Extrai rotas Ziggy da página /start
        2) Encontra URIs reais de get.user.logged, set.user, etc.
        3) Chama cada endpoint relevante
        """
        self._ensure_authenticated()
        results: dict[str, Any] = {}

        # Passo 1: Extrair rotas Ziggy
        ziggy_routes = self._extract_ziggy_routes()

        # Mostrar as rotas relevantes (user, vinculo, start, dashboard)
        relevant_keys = [
            k for k in ziggy_routes
            if any(x in k.lower() for x in [
                "user", "vinculo", "start", "dashboard", "login",
                "set", "logged", "unidade", "perfil", "matricula",
            ])
        ]
        results["ziggy_relevant_routes"] = {
            k: ziggy_routes[k] for k in relevant_keys
        }

        # Passo 2: Tentar cada rota de usuário
        for route_name in ["get.user.logged", "get-user-logged", "start"]:
            route = ziggy_routes.get(route_name)
            if not route:
                continue
            uri = route.get("uri", "")
            methods = route.get("methods", [])
            method = "POST" if "POST" in methods else "GET"

            try:
                resp = self._api_request(method, self._url(f"/{uri}"))
                entry: dict[str, Any] = {
                    "route_name": route_name,
                    "uri": uri,
                    "method": method,
                    "status": resp.status_code,
                }
                try:
                    data = resp.json()
                    # Limitar tamanho para não estourar
                    entry["data"] = str(data)[:2000]
                except ValueError:
                    entry["body_preview"] = resp.text[:500]
                results[f"call_{route_name}"] = entry
            except Exception as e:
                results[f"call_{route_name}"] = {"error": str(e)}

        # Passo 3: Tentar set-user se encontrado
        set_user_route = ziggy_routes.get("set.user")
        if set_user_route:
            results["set_user_route_info"] = set_user_route

        return results

    def get_debug_info(self) -> dict[str, Any]:
        """Retorna informações de diagnóstico da última operação."""
        return {
            **self._debug_info,
            "authenticated": self._authenticated,
            "nome_usuario": self.nome_usuario,
            "cpf_partial": self.cpf[:3] + "***" if self.cpf else "",
            "cookies": list(self.session.cookies.keys()),
            "xsrf_token_present": bool(self._get_xsrf_token()),
        }

    def debug_test_api(self) -> dict[str, Any]:
        """
        Testa cada endpoint da API e retorna os resultados detalhados.
        Usado para diagnosticar problemas após login.
        """
        results: dict[str, Any] = {}

        if not self._authenticated:
            return {"error": "Não autenticado"}

        # Teste 1: GET /start — sessão ainda válida?
        try:
            resp = self.session.get(
                self._url("/start"),
                allow_redirects=False,
                headers={"X-XSRF-TOKEN": self._get_xsrf_token()},
            )
            results["start_page"] = {
                "status": resp.status_code,
                "location": resp.headers.get("Location", ""),
                "is_redirect_to_login": "/login" in resp.headers.get("Location", ""),
            }
        except Exception as e:
            results["start_page"] = {"error": str(e)}

        # Teste 2: GET cardápio API
        try:
            hoje = datetime.now()
            inicio = hoje.strftime("%d/%m/%Y")
            fim = (hoje + timedelta(days=14)).strftime("%d/%m/%Y")
            period = f"{inicio} - {fim}"

            url = self._route_url("api.refeitorio.refeicao.refeicoes")
            resp = self._api_request("GET", url, params={
                "page": 1, "offset": 14, "period": period,
            })
            body_preview = resp.text[:500] if resp.text else ""
            try:
                json_data = resp.json()
                results["cardapio_api"] = {
                    "status": resp.status_code,
                    "url": url,
                    "is_json": True,
                    "type": type(json_data).__name__,
                    "keys": list(json_data.keys()) if isinstance(json_data, dict) else None,
                    "data_count": (
                        len(json_data.get("data", []))
                        if isinstance(json_data, dict) else
                        (len(json_data) if isinstance(json_data, list) else None)
                    ),
                    "raw_preview": str(json_data)[:500],
                }
            except ValueError:
                results["cardapio_api"] = {
                    "status": resp.status_code,
                    "url": url,
                    "is_json": False,
                    "body_preview": body_preview,
                }
        except OrbitalSessionExpired as e:
            results["cardapio_api"] = {"error": str(e), "session_expired": True}
        except Exception as e:
            results["cardapio_api"] = {"error": str(e)}

        # Teste 3: GET agendamentos API
        try:
            url = self._route_url("api.refeitorio.agendamento.agendamentos")
            resp = self._api_request("GET", url, params={
                "page": 1, "offset": 10,
            })
            try:
                json_data = resp.json()
                results["agendamentos_api"] = {
                    "status": resp.status_code,
                    "url": url,
                    "is_json": True,
                    "type": type(json_data).__name__,
                    "keys": list(json_data.keys()) if isinstance(json_data, dict) else None,
                    "raw_preview": str(json_data)[:500],
                }
            except ValueError:
                results["agendamentos_api"] = {
                    "status": resp.status_code,
                    "url": url,
                    "is_json": False,
                    "body_preview": resp.text[:500],
                }
        except OrbitalSessionExpired as e:
            results["agendamentos_api"] = {"error": str(e), "session_expired": True}
        except Exception as e:
            results["agendamentos_api"] = {"error": str(e)}

        return results

    # ── Cardápio ─────────────────────────────────────────────────

    def get_cardapio(self, inicio: str | None = None, fim: str | None = None) -> list[dict]:
        """
        Busca o cardápio da semana.

        Args:
            inicio: Data início DD/MM/YYYY (default: hoje)
            fim: Data fim DD/MM/YYYY (default: hoje + 14 dias)

        Returns:
            Lista de dicts com o cardápio de cada dia.
        """
        self._ensure_authenticated()

        if not inicio:
            hoje = datetime.now()
            inicio = hoje.strftime("%d/%m/%Y")
            fim = (hoje + timedelta(days=14)).strftime("%d/%m/%Y")

        period = f"{inicio} - {fim}"

        url = self._route_url("api.refeitorio.refeicao.refeicoes")
        logger.info(f"Buscando cardápio: {url} | period={period}")

        resp = self._api_request("GET", url, params={
            "page": 1,
            "offset": 14,
            "period": period,
        })

        logger.info(
            f"Cardápio response: status={resp.status_code}, "
            f"content-type={resp.headers.get('Content-Type', '')}"
        )

        if resp.status_code != 200:
            logger.error(f"Erro ao buscar cardápio: {resp.status_code} | body={resp.text[:300]}")
            return []

        try:
            data = resp.json()
        except ValueError:
            logger.error(f"Resposta do cardápio não é JSON: {resp.text[:300]}")
            return []

        logger.debug(f"Cardápio raw response: {str(data)[:500]}")

        # Orbital retorna: {error, message, response: [{current_page, data: [...items...]}]}
        # Extrair os itens da estrutura paginada do Laravel
        items = []
        if isinstance(data, dict):
            response = data.get("response", data)
            if isinstance(response, list) and response:
                # response é uma lista; o primeiro elemento contém paginação
                page_obj = response[0]
                if isinstance(page_obj, dict):
                    items = page_obj.get("data", [])
                else:
                    items = response  # fallback: lista direta
            elif isinstance(response, dict):
                items = response.get("data", [])
            else:
                items = data.get("data", [])
        elif isinstance(data, list):
            items = data
        else:
            logger.error(f"Tipo inesperado de resposta do cardápio: {type(data)}")
            return []

        logger.info(f"Cardápio: {len(items)} item(s) encontrado(s)")

        cardapio = []
        for item in items:
            dia_str = item.get("dia_da_refeicao", "")
            try:
                if "/" in dia_str:
                    dt = datetime.strptime(dia_str, "%d/%m/%Y")
                elif "-" in dia_str:
                    dt = datetime.strptime(dia_str[:10], "%Y-%m-%d")
                else:
                    logger.warning(f"Formato de data inesperado: {dia_str}")
                    continue
                data_fmt = dt.strftime("%Y-%m-%d")
                dia_semana = DIAS_SEMANA[dt.weekday()]
            except ValueError:
                data_fmt = dia_str
                dia_semana = ""

            refeicoes = []
            for codigo, info in MEAL_CODES.items():
                descricao = item.get(info["field"])
                if descricao and str(descricao).strip():
                    refeicoes.append({
                        "tipo": codigo,
                        "nome": info["nome"],
                        "descricao": str(descricao).strip(),
                    })

            cardapio.append({
                "data": data_fmt,
                "dia_semana": dia_semana,
                "refeicoes": refeicoes,
            })

        return cardapio

    # ── Agendamentos ─────────────────────────────────────────────

    def get_agendamentos(self, inicio: str | None = None, fim: str | None = None) -> list[dict]:
        """Lista os agendamentos do usuário."""
        self._ensure_authenticated()

        if not inicio:
            hoje = datetime.now()
            inicio = hoje.strftime("%d/%m/%Y")
            fim = (hoje + timedelta(days=14)).strftime("%d/%m/%Y")

        period = f"{inicio} - {fim}"

        url = self._route_url("api.refeitorio.agendamento.agendamentos")
        resp = self._api_request("GET", url, params={
            "page": 1,
            "offset": 50,
            "period": period,
        })

        if resp.status_code != 200:
            logger.error(f"Erro ao buscar agendamentos: {resp.status_code}")
            return []

        try:
            data = resp.json()
        except ValueError:
            return []

        # Orbital retorna: {error, message, response: [{current_page, data: [...]}]}
        items = []
        if isinstance(data, dict):
            response = data.get("response", data)
            if isinstance(response, list) and response:
                page_obj = response[0]
                if isinstance(page_obj, dict):
                    items = page_obj.get("data", [])
                else:
                    items = response
            elif isinstance(response, dict):
                items = response.get("data", [])
            else:
                items = data.get("data", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []

        agendamentos = []
        for item in items:
            # Mapear tipo de refeição para código
            tipo_nome = item.get("tipo_refeicao", "")
            tipo_codigo = ""
            for codigo, info in MEAL_CODES.items():
                if info["nome"].lower() in tipo_nome.lower() or codigo.lower() in tipo_nome.lower():
                    tipo_codigo = codigo
                    break

            dia_str = item.get("dia_da_refeicao", "")
            try:
                if "/" in dia_str:
                    dt = datetime.strptime(dia_str, "%d/%m/%Y")
                    dia_str = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

            agendamentos.append({
                "id": item.get("id", 0),
                "dia": dia_str,
                "tipo_refeicao": tipo_nome,
                "tipo_codigo": tipo_codigo,
                "confirmado": bool(item.get("tipo_refeicao_confirmacao", False)),
            })

        return agendamentos

    def agendar(self, dia: str, refeicao: str) -> dict:
        """Agenda uma refeição para um dia específico."""
        self._ensure_authenticated()

        if refeicao not in MEAL_CODES:
            raise OrbitalError(f"Código de refeição inválido: {refeicao}")

        # Montar body com todos os campos, ativando apenas o selecionado
        body: dict[str, Any] = {"dia_da_refeicao": dia}
        for field in ALL_MEAL_FIELDS:
            body[field] = False
        body[MEAL_CODES[refeicao]["field"]] = True

        url = self._route_url("refeitorio.agendamento.store")
        resp = self._api_request("POST", url, json=body)

        if resp.status_code in (200, 201):
            logger.info(f"Agendamento realizado: {dia} - {MEAL_CODES[refeicao]['nome']}")
            try:
                return resp.json()
            except ValueError:
                return {"success": True, "message": "Agendamento realizado"}

        # Tratar erros
        try:
            error_data = resp.json()
            error_msg = error_data.get("message", "")
            if not error_msg:
                errors = error_data.get("errors", {})
                error_msg = "; ".join(
                    msg for msgs in errors.values()
                    for msg in (msgs if isinstance(msgs, list) else [msgs])
                )
        except ValueError:
            error_msg = f"Erro {resp.status_code}: {resp.text[:100]}"

        raise OrbitalError(f"Falha ao agendar: {error_msg}")

    def desagendar(self, agendamento_id: int) -> dict:
        """Cancela um agendamento."""
        self._ensure_authenticated()

        url = self._route_url(
            "refeitorio.agendamento.destroy",
            params={"id": agendamento_id},
        )

        # Laravel usa _method: "delete" para DELETE via POST
        resp = self._api_request("POST", url, json={"_method": "delete"})

        if resp.status_code in (200, 204):
            logger.info(f"Agendamento {agendamento_id} cancelado")
            try:
                return resp.json()
            except ValueError:
                return {"success": True, "message": "Agendamento cancelado"}

        try:
            error_data = resp.json()
            error_msg = error_data.get("message", f"Erro {resp.status_code}")
        except ValueError:
            error_msg = f"Erro {resp.status_code}"

        raise OrbitalError(f"Falha ao desagendar: {error_msg}")

    def is_session_valid(self) -> bool:
        """Verifica se a sessão no Orbital ainda é válida."""
        if not self._authenticated:
            return False

        try:
            resp = self.session.get(
                self._url("/start"),
                allow_redirects=False,
                headers={"X-XSRF-TOKEN": self._get_xsrf_token()},
            )
            # 200 = sessão OK, redirect para /login = expirou
            if resp.status_code == 200:
                return True
            if resp.status_code in (301, 302):
                if "/login" in resp.headers.get("Location", ""):
                    self._authenticated = False
                    return False
            return resp.status_code == 200
        except Exception:
            self._authenticated = False
            return False

    def logout(self) -> None:
        """Encerra a sessão."""
        try:
            self._api_request("POST", self._url("/logout"))
        except Exception:
            pass
        finally:
            self._authenticated = False
            self.session.close()
