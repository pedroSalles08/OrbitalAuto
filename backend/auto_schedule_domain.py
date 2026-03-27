from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import re
import unicodedata
from typing import Any, Iterable, Literal, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WeekdayCode = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WEEKDAY_CODES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
WeeklyRules = Mapping[str, Iterable[str]]


@dataclass(frozen=True)
class ScheduleItem:
    dia: str
    refeicao: str


@dataclass
class ReconciliationPlan:
    candidates: list[ScheduleItem] = field(default_factory=list)
    already_scheduled: int = 0
    skipped_unavailable: int = 0
    skipped_outside_window: int = 0
    skipped_out_of_range: int = 0

    @property
    def skipped(self) -> int:
        return (
            self.skipped_unavailable
            + self.skipped_outside_window
            + self.skipped_out_of_range
        )


def get_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid timezone: {timezone_name}") from exc


def local_now(timezone_name: str, now: datetime | None = None) -> datetime:
    timezone = get_timezone(timezone_name)
    if now is None:
        return datetime.now(timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone)
    return now.astimezone(timezone)


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def weekday_code_for_date(value: str) -> str:
    return WEEKDAY_CODES[parse_iso_date(value).weekday()]


def build_period_strings(now: datetime, lookahead_days: int) -> tuple[str, str]:
    start = now.date()
    end = start + timedelta(days=lookahead_days)
    return start.strftime("%d/%m/%Y"), end.strftime("%d/%m/%Y")


def can_schedule(dia: str, now: datetime) -> tuple[bool, str]:
    try:
        data_refeicao = parse_iso_date(dia)
    except ValueError:
        return False, "Data invalida"

    hoje = now.date()

    if data_refeicao < hoje:
        return False, "Data ja passou"

    if data_refeicao == hoje:
        return False, "Nao e possivel agendar para hoje (prazo: ate 17h de ontem)"

    if data_refeicao == hoje + timedelta(days=1) and now.hour >= 17:
        return False, "Prazo expirado (agendamento ate 17h do dia anterior)"

    return True, "OK"


def can_unschedule(dia: str, now: datetime) -> tuple[bool, str]:
    try:
        data_refeicao = parse_iso_date(dia)
    except ValueError:
        return False, "Data invalida"

    hoje = now.date()

    if data_refeicao < hoje:
        return False, "Data ja passou"

    if data_refeicao == hoje and now.hour >= 9:
        return False, "Prazo expirado (desagendamento ate 9h do dia da refeicao)"

    return True, "OK"


def reconcile_auto_schedule(
    cardapio: Iterable[dict[str, Any]],
    agendamentos: Iterable[dict[str, Any]],
    weekly_rules: WeeklyRules,
    now: datetime,
    lookahead_days: int,
) -> ReconciliationPlan:
    plan = ReconciliationPlan()
    rules = {
        str(weekday).upper(): tuple(
            dict.fromkeys(str(meal).upper() for meal in meals if meal)
        )
        for weekday, meals in (weekly_rules or {}).items()
    }
    existing = {
        (str(item.get("dia", "")), str(item.get("tipo_codigo", "")).upper())
        for item in agendamentos
    }
    today = now.date()
    last_day = today + timedelta(days=lookahead_days)

    for dia in cardapio:
        dia_str = str(dia.get("data", ""))
        try:
            dia_date = parse_iso_date(dia_str)
        except ValueError:
            continue

        weekday_code = weekday_code_for_date(dia_str)
        desired_meals = rules.get(weekday_code, ())
        available = {
            str(refeicao.get("tipo", "")).upper()
            for refeicao in dia.get("refeicoes", [])
        }

        for meal in desired_meals:
            if meal not in available:
                plan.skipped_unavailable += 1
                continue

            if dia_date < today or dia_date > last_day:
                plan.skipped_out_of_range += 1
                continue

            if (dia_str, meal) in existing:
                plan.already_scheduled += 1
                continue

            allowed, _ = can_schedule(dia_str, now)
            if not allowed:
                plan.skipped_outside_window += 1
                continue

            plan.candidates.append(ScheduleItem(dia=dia_str, refeicao=meal))

    return plan


def is_already_scheduled_error(message: str) -> bool:
    normalized = _normalize(message)
    patterns = (
        "ja agendad",
        "agendamento ja realizad",
        "already schedul",
        "ja existe agendamento",
    )
    return any(pattern in normalized for pattern in patterns)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
