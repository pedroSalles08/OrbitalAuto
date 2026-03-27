from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import requests


WEEKDAY_CODES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class SmokeError(RuntimeError):
    """Erro esperado do smoke test."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test dos endpoints do auto scheduler.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("ORBITALAUTO_BASE_URL", "http://127.0.0.1:8000"),
        help="URL base do backend.",
    )
    parser.add_argument(
        "--access-user",
        default=os.getenv("BASIC_AUTH_USER", ""),
        help="Usuario da barreira simples, se habilitada.",
    )
    parser.add_argument(
        "--access-pass",
        default=os.getenv("BASIC_AUTH_PASS", ""),
        help="Senha da barreira simples, se habilitada.",
    )
    parser.add_argument(
        "--app-token",
        default=os.getenv("ORBITALAUTO_APP_TOKEN", ""),
        help="Token Bearer de uma sessao valida do OrbitalAuto.",
    )
    parser.add_argument(
        "--app-cpf",
        default=os.getenv("ORBITALAUTO_APP_CPF", ""),
        help="CPF para fazer login no OrbitalAuto e obter token automaticamente.",
    )
    parser.add_argument(
        "--app-password",
        default=os.getenv("ORBITALAUTO_APP_PASSWORD", ""),
        help="Senha do Orbital para fazer login no OrbitalAuto.",
    )
    parser.add_argument(
        "--config-json",
        default="",
        help="JSON inline para PUT /api/auto-schedule/config.",
    )
    parser.add_argument(
        "--config-file",
        default="",
        help="Arquivo JSON para PUT /api/auto-schedule/config.",
    )
    parser.add_argument(
        "--apply-minimal-config",
        action="store_true",
        help="Salva uma configuracao minima habilitada com um unico dia/refeicao.",
    )
    parser.add_argument(
        "--config-weekday",
        default="MON",
        help="Dia usado com --apply-minimal-config (MON..SUN).",
    )
    parser.add_argument(
        "--config-meal",
        default="AL",
        help="Refeicao usada com --apply-minimal-config (ex.: AL, JA).",
    )
    parser.add_argument(
        "--config-duration-mode",
        default="30d",
        help="duration_mode usado ao salvar configuracao.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Dispara POST /api/auto-schedule/run apos consultar status.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=0,
        help="Espera esse tempo e consulta o status novamente.",
    )
    parser.add_argument(
        "--require-credentials",
        action="store_true",
        help="Falha se has_credentials vier false.",
    )
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="Falha se a execucao manual nao retornar success=true.",
    )
    parser.add_argument(
        "--validate-hosted-smoke",
        action="store_true",
        help=(
            "Valida automaticamente os criterios da Fase 1: "
            "run manual, success, finished_at, session source e "
            "last_successful_run_at atualizado."
        ),
    )
    parser.add_argument(
        "--fetch-agendamentos",
        action="store_true",
        help="Consulta GET /api/agendamentos ao final do script.",
    )
    parser.add_argument(
        "--watch-seconds",
        type=int,
        default=0,
        help="Mantem o servico acordado consultando o status durante essa janela.",
    )
    parser.add_argument(
        "--watch-interval-seconds",
        type=int,
        default=300,
        help="Intervalo entre consultas de status durante --watch-seconds.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Timeout HTTP em segundos.",
    )
    return parser.parse_args()


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def print_payload(title: str, payload: dict) -> None:
    print(f"\n== {title} ==")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: float,
    json_body: dict[str, Any] | None = None,
) -> tuple[requests.Response, dict]:
    response = session.request(
        method,
        url,
        timeout=timeout,
        allow_redirects=False,
        json=json_body,
    )

    try:
        payload = response.json()
    except ValueError:
        body = response.text.strip()
        if response.status_code == 401 and "Acesso restrito" in body:
            raise SmokeError(
                "API bloqueada pela barreira simples. Forneca "
                "--access-user/--access-pass ou passe primeiro pela barreira."
            ) from None
        raise SmokeError(
            f"Resposta nao JSON em {url} "
            f"(status={response.status_code}, body={body[:200]!r})."
        ) from None

    if response.status_code >= 400:
        detail = str(payload.get("detail", ""))
        if response.status_code == 401 and ("Token" in detail or "Sess" in detail):
            raise SmokeError(
                "API bloqueada pela sessao do OrbitalAuto. Faca login no app "
                "e passe --app-token ou --app-cpf/--app-password."
            )
        raise SmokeError(
            f"Requisicao falhou em {url} "
            f"(status={response.status_code}, payload={payload})."
        )

    if not isinstance(payload, dict):
        raise SmokeError(f"Payload inesperado em {url}: {type(payload).__name__}")

    return response, payload


def login_access_gate(
    session: requests.Session,
    *,
    base_url: str,
    username: str,
    password: str,
    timeout: float,
) -> None:
    response = session.post(
        build_url(base_url, "/__access/login"),
        data={"username": username, "password": password},
        timeout=timeout,
        allow_redirects=False,
    )

    if response.status_code == 303:
        return

    body = response.text.strip()
    raise SmokeError(
        "Falha ao autenticar na barreira simples "
        f"(status={response.status_code}, body={body[:200]!r})."
    )


def login_app(
    session: requests.Session,
    *,
    base_url: str,
    cpf: str,
    password: str,
    timeout: float,
) -> dict[str, Any]:
    _, payload = request_json(
        session,
        "POST",
        build_url(base_url, "/api/auth/login"),
        timeout=timeout,
        json_body={"cpf": cpf, "senha": password},
    )

    token = str(payload.get("token", "")).strip()
    if not token:
        raise SmokeError("Login no app nao retornou token.")

    session.headers["Authorization"] = f"Bearer {token}"
    return payload


def get_status(
    session: requests.Session,
    *,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    _, payload = request_json(
        session,
        "GET",
        build_url(base_url, "/api/auto-schedule/status"),
        timeout=timeout,
    )
    return payload


def save_config(
    session: requests.Session,
    *,
    base_url: str,
    timeout: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    _, response_payload = request_json(
        session,
        "PUT",
        build_url(base_url, "/api/auto-schedule/config"),
        timeout=timeout,
        json_body=payload,
    )
    return response_payload


def run_auto_scheduler(
    session: requests.Session,
    *,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    _, payload = request_json(
        session,
        "POST",
        build_url(base_url, "/api/auto-schedule/run"),
        timeout=timeout,
    )
    return payload


def get_agendamentos(
    session: requests.Session,
    *,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    _, payload = request_json(
        session,
        "GET",
        build_url(base_url, "/api/agendamentos"),
        timeout=timeout,
    )
    return payload


def build_minimal_config(
    *,
    weekday: str,
    meal: str,
    duration_mode: str,
) -> dict[str, Any]:
    normalized_weekday = weekday.upper().strip()
    normalized_meal = meal.upper().strip()
    normalized_duration = duration_mode.strip() or "30d"

    if normalized_weekday not in WEEKDAY_CODES:
        raise SmokeError(
            "Dia invalido para configuracao minima: "
            f"{weekday!r}. Use um de {', '.join(WEEKDAY_CODES)}."
        )
    if not normalized_meal:
        raise SmokeError("Refeicao vazia em --config-meal.")

    weekly_rules = {code: [] for code in WEEKDAY_CODES}
    weekly_rules[normalized_weekday] = [normalized_meal]
    return {
        "enabled": True,
        "weekly_rules": weekly_rules,
        "duration_mode": normalized_duration,
    }


def load_config_payload(args: argparse.Namespace) -> dict[str, Any] | None:
    selected_sources = [
        bool(args.config_json),
        bool(args.config_file),
        bool(args.apply_minimal_config),
    ]
    if sum(selected_sources) > 1:
        raise SmokeError(
            "Escolha apenas uma fonte de configuracao: "
            "--config-json, --config-file ou --apply-minimal-config."
        )

    if args.config_json:
        try:
            payload = json.loads(args.config_json)
        except json.JSONDecodeError as exc:
            raise SmokeError(f"JSON invalido em --config-json: {exc}") from exc
    elif args.config_file:
        config_path = Path(args.config_file)
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise SmokeError(f"Nao foi possivel ler {config_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SmokeError(f"JSON invalido em {config_path}: {exc}") from exc
    elif args.apply_minimal_config:
        payload = build_minimal_config(
            weekday=args.config_weekday,
            meal=args.config_meal,
            duration_mode=args.config_duration_mode,
        )
    else:
        return None

    if not isinstance(payload, dict):
        raise SmokeError(
            "Payload de configuracao invalido: esperado objeto JSON no topo."
        )

    return payload


def extract_session_source(run_payload: dict[str, Any]) -> str:
    if run_payload.get("used_existing_session"):
        return "used_existing_session"
    if run_payload.get("login_performed"):
        return "login_performed"
    raise SmokeError(
        "Execucao manual nao informou reuse de sessao nem login automatico."
    )


def validate_hosted_smoke(
    *,
    baseline_status: dict[str, Any],
    run_payload: dict[str, Any],
    follow_up_status: dict[str, Any],
) -> dict[str, Any]:
    if not baseline_status.get("has_credentials"):
        raise SmokeError("Status inicial retornou has_credentials=false.")

    if run_payload.get("trigger") != "manual":
        raise SmokeError(
            "Execucao manual retornou trigger inesperado: "
            f"{run_payload.get('trigger')!r}."
        )
    if not run_payload.get("success"):
        raise SmokeError(
            "Execucao manual retornou success=false: "
            f"{run_payload.get('last_error') or run_payload.get('errors')}."
        )
    if not run_payload.get("finished_at"):
        raise SmokeError("Execucao manual nao retornou finished_at.")

    session_source = extract_session_source(run_payload)
    follow_up_last_run = follow_up_status.get("last_run")
    if not isinstance(follow_up_last_run, dict):
        raise SmokeError("Status apos execucao nao trouxe last_run.")
    if follow_up_last_run.get("trigger") != "manual":
        raise SmokeError(
            "Status apos execucao nao registrou last_run.trigger='manual'."
        )
    if not follow_up_last_run.get("finished_at"):
        raise SmokeError(
            "Status apos execucao nao registrou last_run.finished_at."
        )

    baseline_last_success = baseline_status.get("last_successful_run_at")
    follow_up_last_success = follow_up_status.get("last_successful_run_at")
    if not follow_up_last_success:
        raise SmokeError(
            "Status apos execucao nao registrou last_successful_run_at."
        )
    if follow_up_last_success == baseline_last_success:
        raise SmokeError(
            "last_successful_run_at nao mudou entre baseline e follow-up."
        )

    return {
        "result": "pass",
        "session_source": session_source,
        "baseline_last_successful_run_at": baseline_last_success,
        "follow_up_last_successful_run_at": follow_up_last_success,
        "next_run_at": follow_up_status.get("next_run_at"),
    }


def watch_status(
    session: requests.Session,
    *,
    base_url: str,
    timeout: float,
    total_seconds: int,
    interval_seconds: int,
) -> list[dict[str, Any]]:
    if total_seconds <= 0:
        return []
    if interval_seconds <= 0:
        raise SmokeError("--watch-interval-seconds deve ser > 0.")

    snapshots: list[dict[str, Any]] = []
    deadline = time.time() + total_seconds
    iteration = 1

    while True:
        payload = get_status(session, base_url=base_url, timeout=timeout)
        snapshots.append(payload)
        print_payload(f"watch-status-{iteration}", payload)

        remaining = deadline - time.time()
        if remaining <= 0:
            break

        sleep_for = min(interval_seconds, max(0, int(remaining)))
        if sleep_for <= 0:
            break
        print(f"\nAguardando {sleep_for}s...")
        time.sleep(sleep_for)
        iteration += 1

    return snapshots


def main() -> int:
    args = parse_args()
    session = requests.Session()
    session.headers.update({"User-Agent": "orbitalauto-smoke/2.0"})

    if args.access_user or args.access_pass:
        if not (args.access_user and args.access_pass):
            raise SmokeError(
                "Forneca os dois parametros da barreira simples: "
                "--access-user e --access-pass."
            )
        login_access_gate(
            session,
            base_url=args.base_url,
            username=args.access_user,
            password=args.access_pass,
            timeout=args.timeout,
        )
        print("Barreira simples autenticada.")

    if args.app_token:
        session.headers["Authorization"] = f"Bearer {args.app_token}"
        print("Sessao do app carregada via --app-token.")
    elif args.app_cpf or args.app_password:
        if not (args.app_cpf and args.app_password):
            raise SmokeError(
                "Forneca os dois parametros de login do app: "
                "--app-cpf e --app-password."
            )
        login_payload = login_app(
            session,
            base_url=args.base_url,
            cpf=args.app_cpf,
            password=args.app_password,
            timeout=args.timeout,
        )
        print_payload("app-login", login_payload)

    config_payload = load_config_payload(args)
    if config_payload is not None:
        if not config_payload.get("orbital_password") and args.app_password:
            config_payload["orbital_password"] = args.app_password
        saved_config = save_config(
            session,
            base_url=args.base_url,
            timeout=args.timeout,
            payload=config_payload,
        )
        print_payload("config", saved_config)

    status_payload = get_status(
        session,
        base_url=args.base_url,
        timeout=args.timeout,
    )
    print_payload("status", status_payload)

    if args.require_credentials and not status_payload.get("has_credentials"):
        raise SmokeError("Status retornou has_credentials=false.")

    run_payload: dict[str, Any] | None = None
    if args.run:
        run_payload = run_auto_scheduler(
            session,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        print_payload("run", run_payload)

        if args.require_success and not run_payload.get("success"):
            raise SmokeError(
                "Execucao manual retornou success=false: "
                f"{run_payload.get('last_error') or run_payload.get('errors')}"
            )

    follow_up_status: dict[str, Any] | None = None
    if args.wait_seconds > 0:
        print(f"\nAguardando {args.wait_seconds}s...")
        time.sleep(args.wait_seconds)

    if args.run or args.wait_seconds > 0 or args.validate_hosted_smoke:
        follow_up_status = get_status(
            session,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        print_payload("status-after-wait", follow_up_status)

    if args.validate_hosted_smoke:
        if run_payload is None:
            raise SmokeError("--validate-hosted-smoke exige --run.")
        if follow_up_status is None:
            raise SmokeError(
                "Nao foi possivel obter o status apos a execucao manual."
            )
        validation_payload = validate_hosted_smoke(
            baseline_status=status_payload,
            run_payload=run_payload,
            follow_up_status=follow_up_status,
        )
        print_payload("validation", validation_payload)

    if args.fetch_agendamentos:
        agendamentos_payload = get_agendamentos(
            session,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        print_payload("agendamentos", agendamentos_payload)

    if args.watch_seconds > 0:
        watch_status(
            session,
            base_url=args.base_url,
            timeout=args.timeout,
            total_seconds=args.watch_seconds,
            interval_seconds=args.watch_interval_seconds,
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
