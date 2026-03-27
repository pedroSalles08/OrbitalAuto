from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any

from auto_schedule_domain import WEEKDAY_CODES
from orbital_client import MEAL_CODES


logger = logging.getLogger("auto_schedule_store")

DURATION_MODES = ("30d", "90d", "end_of_year")


@dataclass(frozen=True)
class AutoScheduleConfig:
    enabled: bool = False
    weekly_rules: dict[str, tuple[str, ...]] | None = None
    duration_mode: str = "30d"
    active_until: date | None = None
    updated_at: datetime | None = None
    last_successful_run_at: datetime | None = None
    last_primary_attempt_at: datetime | None = None
    last_fallback_attempt_at: datetime | None = None

    def normalized(self) -> "AutoScheduleConfig":
        weekly_rules = _normalize_weekly_rules(self.weekly_rules)
        duration_mode = (self.duration_mode or "30d").strip() or "30d"
        return AutoScheduleConfig(
            enabled=bool(self.enabled),
            weekly_rules=weekly_rules,
            duration_mode=duration_mode,
            active_until=self.active_until,
            updated_at=self.updated_at,
            last_successful_run_at=self.last_successful_run_at,
            last_primary_attempt_at=self.last_primary_attempt_at,
            last_fallback_attempt_at=self.last_fallback_attempt_at,
        )

    def validate(self) -> str | None:
        if self.duration_mode not in DURATION_MODES:
            return (
                "AUTO_SCHEDULE duration_mode must be one of: "
                + ", ".join(DURATION_MODES)
            )

        weekly_rules = _normalize_weekly_rules(self.weekly_rules)
        invalid_weekdays = [
            weekday for weekday in weekly_rules if weekday not in WEEKDAY_CODES
        ]
        if invalid_weekdays:
            return (
                "AUTO_SCHEDULE weekly_rules has invalid weekday values: "
                + ", ".join(sorted(invalid_weekdays))
            )

        invalid_meals = sorted(
            {
                meal
                for meals in weekly_rules.values()
                for meal in meals
                if meal not in MEAL_CODES
            }
        )
        if invalid_meals:
            return (
                "AUTO_SCHEDULE weekly_rules has invalid meal values: "
                + ", ".join(sorted(invalid_meals))
            )

        has_any_rule = any(weekly_rules.get(weekday) for weekday in WEEKDAY_CODES)
        if self.enabled and not has_any_rule:
            return (
                "Selecione ao menos uma combinacao de dia e refeicao para ativar a "
                "automacao."
            )

        return None

    def is_expired(self, now: datetime) -> bool:
        return self.active_until is not None and now.date() > self.active_until

    def to_payload(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "weekly_rules": _serialize_weekly_rules(self.weekly_rules),
            "duration_mode": self.duration_mode,
            "active_until": self.active_until,
            "updated_at": self.updated_at,
            "last_successful_run_at": self.last_successful_run_at,
        }


@dataclass(frozen=True)
class AutoScheduleProfile:
    cpf: str
    enabled: bool = False
    weekly_rules: dict[str, tuple[str, ...]] | None = None
    duration_mode: str = "30d"
    active_until: date | None = None
    updated_at: datetime | None = None
    last_successful_run_at: datetime | None = None
    last_primary_attempt_at: datetime | None = None
    last_fallback_attempt_at: datetime | None = None
    encrypted_password: str | None = None
    credentials_updated_at: datetime | None = None

    def normalized(self) -> "AutoScheduleProfile":
        config = self.to_config().normalized()
        encrypted_password = (
            str(self.encrypted_password).strip() if self.encrypted_password else None
        )
        if encrypted_password == "":
            encrypted_password = None
        normalized_cpf = _normalize_cpf(self.cpf)
        return AutoScheduleProfile(
            cpf=normalized_cpf,
            enabled=config.enabled,
            weekly_rules=config.weekly_rules,
            duration_mode=config.duration_mode,
            active_until=config.active_until,
            updated_at=config.updated_at,
            last_successful_run_at=config.last_successful_run_at,
            last_primary_attempt_at=config.last_primary_attempt_at,
            last_fallback_attempt_at=config.last_fallback_attempt_at,
            encrypted_password=encrypted_password,
            credentials_updated_at=self.credentials_updated_at,
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.encrypted_password)

    def validate(self) -> str | None:
        return self.to_config().validate()

    def is_expired(self, now: datetime) -> bool:
        return self.to_config().is_expired(now)

    def to_config(self) -> AutoScheduleConfig:
        return AutoScheduleConfig(
            enabled=self.enabled,
            weekly_rules=self.weekly_rules,
            duration_mode=self.duration_mode,
            active_until=self.active_until,
            updated_at=self.updated_at,
            last_successful_run_at=self.last_successful_run_at,
            last_primary_attempt_at=self.last_primary_attempt_at,
            last_fallback_attempt_at=self.last_fallback_attempt_at,
        )

    def to_payload(self) -> dict[str, object]:
        payload = self.to_config().to_payload()
        payload.update(
            {
                "has_credentials": self.has_credentials,
                "credentials_updated_at": self.credentials_updated_at,
            }
        )
        return payload

    @classmethod
    def empty(cls, cpf: str) -> "AutoScheduleProfile":
        return cls(cpf=_normalize_cpf(cpf)).normalized()


def calculate_active_until(duration_mode: str, now: datetime) -> date:
    today = now.date()
    if duration_mode == "30d":
        return today + timedelta(days=30)
    if duration_mode == "90d":
        return today + timedelta(days=90)
    return date(today.year, 12, 31)


class AutoScheduleConfigStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> AutoScheduleConfig:
        if not self._path.exists():
            return AutoScheduleConfig()

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8-sig"))
        except Exception:
            logger.exception("Failed to load auto schedule config from %s", self._path)
            return AutoScheduleConfig()

        try:
            return _config_from_json(payload)
        except Exception:
            logger.exception("Invalid auto schedule config in %s", self._path)
            return AutoScheduleConfig()

    def save(self, config: AutoScheduleConfig) -> AutoScheduleConfig:
        normalized = config.normalized()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(_config_to_json(normalized), indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._path)
        return normalized


class AutoScheduleProfileStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load_all(self) -> dict[str, AutoScheduleProfile]:
        if not self._path.exists():
            return {}

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8-sig"))
        except Exception:
            logger.exception(
                "Failed to load auto schedule profiles from %s",
                self._path,
            )
            return {}

        try:
            return _profiles_from_json(payload)
        except Exception:
            logger.exception(
                "Invalid auto schedule profiles in %s",
                self._path,
            )
            return {}

    def load(self, cpf: str) -> AutoScheduleProfile | None:
        normalized_cpf = _normalize_cpf(cpf)
        if not normalized_cpf:
            return None
        return self.load_all().get(normalized_cpf)

    def save(self, profile: AutoScheduleProfile) -> AutoScheduleProfile:
        normalized = profile.normalized()
        if not normalized.cpf:
            raise ValueError("Auto schedule profile requires a CPF.")

        profiles = self.load_all()
        profiles[normalized.cpf] = normalized
        self.save_all(profiles)
        return normalized

    def save_all(
        self,
        profiles: dict[str, AutoScheduleProfile],
    ) -> dict[str, AutoScheduleProfile]:
        normalized_profiles = {
            normalized.cpf: normalized
            for profile in profiles.values()
            if (normalized := profile.normalized()).cpf
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        payload = {
            "profiles": {
                cpf: _profile_to_json(profile)
                for cpf, profile in sorted(normalized_profiles.items())
            }
        }
        temp_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._path)
        return normalized_profiles


def _config_from_json(payload: dict[str, Any]) -> AutoScheduleConfig:
    raw_weekly_rules = payload.get("weekly_rules")
    if isinstance(raw_weekly_rules, dict):
        weekly_rules = raw_weekly_rules
    else:
        weekly_rules = _legacy_weekly_rules_from_meals(payload.get("meals", []))

    return AutoScheduleConfig(
        enabled=bool(payload.get("enabled", False)),
        weekly_rules=weekly_rules,
        duration_mode=str(payload.get("duration_mode", "30d")),
        active_until=_parse_date(payload.get("active_until")),
        updated_at=_parse_datetime(payload.get("updated_at")),
        last_successful_run_at=_parse_datetime(payload.get("last_successful_run_at")),
        last_primary_attempt_at=_parse_datetime(payload.get("last_primary_attempt_at")),
        last_fallback_attempt_at=_parse_datetime(
            payload.get("last_fallback_attempt_at")
        ),
    ).normalized()


def _config_to_json(config: AutoScheduleConfig) -> dict[str, Any]:
    return {
        "enabled": config.enabled,
        "weekly_rules": _serialize_weekly_rules(config.weekly_rules),
        "duration_mode": config.duration_mode,
        "active_until": config.active_until.isoformat() if config.active_until else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        "last_successful_run_at": (
            config.last_successful_run_at.isoformat()
            if config.last_successful_run_at
            else None
        ),
        "last_primary_attempt_at": (
            config.last_primary_attempt_at.isoformat()
            if config.last_primary_attempt_at
            else None
        ),
        "last_fallback_attempt_at": (
            config.last_fallback_attempt_at.isoformat()
            if config.last_fallback_attempt_at
            else None
        ),
    }


def _profiles_from_json(payload: Any) -> dict[str, AutoScheduleProfile]:
    if not isinstance(payload, dict):
        return {}

    raw_profiles = payload.get("profiles")
    if isinstance(raw_profiles, dict):
        source = raw_profiles
    elif all(isinstance(value, dict) for value in payload.values()):
        source = payload
    else:
        return {}

    profiles: dict[str, AutoScheduleProfile] = {}
    for raw_cpf, raw_profile in source.items():
        if not isinstance(raw_profile, dict):
            continue
        profile = _profile_from_json(str(raw_cpf), raw_profile)
        if profile.cpf:
            profiles[profile.cpf] = profile
    return profiles


def _profile_from_json(raw_cpf: str, payload: dict[str, Any]) -> AutoScheduleProfile:
    raw_weekly_rules = payload.get("weekly_rules")
    if isinstance(raw_weekly_rules, dict):
        weekly_rules = raw_weekly_rules
    else:
        weekly_rules = _legacy_weekly_rules_from_meals(payload.get("meals", []))

    return AutoScheduleProfile(
        cpf=_normalize_cpf(payload.get("cpf", raw_cpf)),
        enabled=bool(payload.get("enabled", False)),
        weekly_rules=weekly_rules,
        duration_mode=str(payload.get("duration_mode", "30d")),
        active_until=_parse_date(payload.get("active_until")),
        updated_at=_parse_datetime(payload.get("updated_at")),
        last_successful_run_at=_parse_datetime(payload.get("last_successful_run_at")),
        last_primary_attempt_at=_parse_datetime(payload.get("last_primary_attempt_at")),
        last_fallback_attempt_at=_parse_datetime(
            payload.get("last_fallback_attempt_at")
        ),
        encrypted_password=_parse_optional_text(payload.get("encrypted_password")),
        credentials_updated_at=_parse_datetime(
            payload.get("credentials_updated_at")
        ),
    ).normalized()


def _profile_to_json(profile: AutoScheduleProfile) -> dict[str, Any]:
    return {
        "cpf": profile.cpf,
        "enabled": profile.enabled,
        "weekly_rules": _serialize_weekly_rules(profile.weekly_rules),
        "duration_mode": profile.duration_mode,
        "active_until": profile.active_until.isoformat() if profile.active_until else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "last_successful_run_at": (
            profile.last_successful_run_at.isoformat()
            if profile.last_successful_run_at
            else None
        ),
        "last_primary_attempt_at": (
            profile.last_primary_attempt_at.isoformat()
            if profile.last_primary_attempt_at
            else None
        ),
        "last_fallback_attempt_at": (
            profile.last_fallback_attempt_at.isoformat()
            if profile.last_fallback_attempt_at
            else None
        ),
        "encrypted_password": profile.encrypted_password,
        "credentials_updated_at": (
            profile.credentials_updated_at.isoformat()
            if profile.credentials_updated_at
            else None
        ),
    }


def _normalize_weekly_rules(
    weekly_rules: dict[str, tuple[str, ...]] | dict[str, list[str]] | None,
) -> dict[str, tuple[str, ...]]:
    normalized_lists: dict[str, list[str]] = {weekday: [] for weekday in WEEKDAY_CODES}
    extra_lists: dict[str, list[str]] = {}

    for raw_weekday, raw_meals in (weekly_rules or {}).items():
        weekday = str(raw_weekday).upper().strip()
        target = (
            normalized_lists[weekday]
            if weekday in normalized_lists
            else extra_lists.setdefault(weekday, [])
        )

        for raw_meal in raw_meals or []:
            meal = str(raw_meal).upper().strip()
            if meal and meal not in target:
                target.append(meal)

    payload = {weekday: tuple(normalized_lists[weekday]) for weekday in WEEKDAY_CODES}
    for weekday, meals in extra_lists.items():
        payload[weekday] = tuple(meals)
    return payload


def _serialize_weekly_rules(
    weekly_rules: dict[str, tuple[str, ...]] | dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    normalized = _normalize_weekly_rules(weekly_rules)
    return {weekday: list(normalized.get(weekday, ())) for weekday in WEEKDAY_CODES}


def _legacy_weekly_rules_from_meals(meals: Any) -> dict[str, tuple[str, ...]]:
    normalized_meals = tuple(
        dict.fromkeys(str(value).upper().strip() for value in (meals or []) if value)
    )
    return {weekday: normalized_meals for weekday in WEEKDAY_CODES}


def _normalize_cpf(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value))


def _parse_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
