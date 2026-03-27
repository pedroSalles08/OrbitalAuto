from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import logging
from typing import Callable, Literal

from auto_schedule_domain import (
    build_period_strings,
    get_timezone,
    is_already_scheduled_error,
    local_now,
    reconcile_auto_schedule,
)
from auto_schedule_store import (
    AutoScheduleConfig,
    AutoScheduleConfigStore,
    calculate_active_until,
)
from orbital_client import OrbitalClient, OrbitalError, OrbitalLoginError, OrbitalSessionExpired
from session_manager import SessionManager


AutoSchedulePhase = Literal["primary", "fallback"]

PRIMARY_DAY = "SAT"
FALLBACK_DAY = "SUN"
PRIMARY_WEEKDAY = 5
FALLBACK_WEEKDAY = 6
SLOT_WINDOW_START = time(hour=8, minute=0)
SLOT_WINDOW_MINUTES = 12 * 60
SLOT_HASH_SALT = "orbitalauto-weekend-slot-v1"


class AutoScheduleConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutoScheduleSettings:
    dry_run: bool
    timezone_name: str
    lookahead_days: int
    cpf: str
    password: str

    @property
    def has_credentials(self) -> bool:
        return bool(self.cpf and self.password)

    @property
    def masked_cpf(self) -> str:
        digits = "".join(ch for ch in self.cpf if ch.isdigit())
        if len(digits) < 3:
            return "***"
        return f"{digits[:3]}***"

    def validation_error(self) -> str | None:
        if self.lookahead_days < 1:
            return "AUTO_SCHEDULE_LOOKAHEAD_DAYS must be >= 1."

        try:
            get_timezone(self.timezone_name)
        except ValueError as exc:
            return str(exc)

        return None


@dataclass
class AutoScheduleRunResult:
    trigger: str
    enabled: bool
    dry_run: bool
    started_at: datetime
    finished_at: datetime | None = None
    success: bool | None = None
    message: str = ""
    used_existing_session: bool = False
    login_performed: bool = False
    candidates_count: int = 0
    scheduled_count: int = 0
    already_scheduled_count: int = 0
    skipped_count: int = 0
    errors: list[str] = field(default_factory=list)
    last_error: str | None = None
    executed: bool = False

    def finish(self, success: bool, message: str) -> "AutoScheduleRunResult":
        self.success = success
        self.message = message
        self.finished_at = self.finished_at or datetime.now(self.started_at.tzinfo)
        if self.errors:
            self.last_error = self.errors[-1]
        return self

    def to_payload(self) -> dict[str, object]:
        return {
            "trigger": self.trigger,
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "success": self.success,
            "message": self.message,
            "used_existing_session": self.used_existing_session,
            "login_performed": self.login_performed,
            "candidates_count": self.candidates_count,
            "scheduled_count": self.scheduled_count,
            "already_scheduled_count": self.already_scheduled_count,
            "skipped_count": self.skipped_count,
            "errors": list(self.errors),
            "last_error": self.last_error,
        }


class AutoScheduler:
    def __init__(
        self,
        session_manager: SessionManager,
        settings: AutoScheduleSettings,
        config_store: AutoScheduleConfigStore,
        orbital_client_factory: Callable[[], OrbitalClient] = OrbitalClient,
        now_provider: Callable[[str], datetime] = local_now,
    ) -> None:
        self._session_manager = session_manager
        self._settings = settings
        self._config_store = config_store
        self._orbital_client_factory = orbital_client_factory
        self._now_provider = now_provider
        self._logger = logging.getLogger("auto_scheduler")
        self._loop_task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()
        self._run_lock = asyncio.Lock()
        self._running = False
        self._next_run_at: datetime | None = None
        self._last_run: AutoScheduleRunResult | None = None
        self._config = self._config_store.load().normalized()
        self._next_run_at = self._compute_next_run_at(self._config, self._now())

    async def start(self) -> None:
        if self._loop_task:
            return

        self._logger.info(
            "Auto scheduler initialized (dry_run=%s timezone=%s config=%s)",
            self._settings.dry_run,
            self._settings.timezone_name,
            getattr(self._config_store, "_path", "<memory>"),
        )
        self._loop_task = asyncio.create_task(self._loop(), name="auto-scheduler")

    async def stop(self) -> None:
        if not self._loop_task:
            return

        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        finally:
            self._loop_task = None
            self._next_run_at = None

    async def run_now(
        self,
        trigger: str = "manual",
        *,
        force: bool = False,
    ) -> dict[str, object]:
        async with self._run_lock:
            self._running = True
            try:
                result = self._run_once(trigger=trigger, force=force)
                if result.success and result.executed and result.finished_at is not None:
                    self._mark_success(result.finished_at)
                self._last_run = result
                self._next_run_at = self._compute_next_run_at(self._config, self._now())
                self._wake_event.set()
                return result.to_payload()
            finally:
                self._running = False

    def config_payload(self) -> dict[str, object]:
        config = self._config
        payload = config.to_payload()
        payload.update(self._slot_payload())
        return payload

    def save_config(
        self,
        *,
        enabled: bool,
        weekly_rules: dict[str, list[str]],
        duration_mode: str,
    ) -> dict[str, object]:
        now = self._now()
        candidate = AutoScheduleConfig(
            enabled=enabled,
            weekly_rules=weekly_rules,
            duration_mode=duration_mode,
            active_until=calculate_active_until(duration_mode, now),
            updated_at=now,
            last_successful_run_at=self._config.last_successful_run_at,
            last_primary_attempt_at=self._config.last_primary_attempt_at,
            last_fallback_attempt_at=self._config.last_fallback_attempt_at,
        ).normalized()

        validation_error = candidate.validate()
        if validation_error:
            raise AutoScheduleConfigError(validation_error)

        self._config = self._config_store.save(candidate)
        self._next_run_at = self._compute_next_run_at(self._config, now)
        self._wake_event.set()
        return self.config_payload()

    def status_payload(self) -> dict[str, object]:
        config = self._config
        next_run_at = self._next_run_at
        if next_run_at is None:
            next_run_at = self._compute_next_run_at(config, self._now())

        payload = {
            "enabled": config.enabled,
            "dry_run": self._settings.dry_run,
            "running": self._running,
            "timezone": self._settings.timezone_name,
            "weekly_rules": config.to_payload()["weekly_rules"],
            "duration_mode": config.duration_mode,
            "active_until": config.active_until,
            "updated_at": config.updated_at,
            "last_successful_run_at": config.last_successful_run_at,
            "has_credentials": self._settings.has_credentials,
            "next_run_at": next_run_at,
            "last_run": self._last_run.to_payload() if self._last_run else None,
        }
        payload.update(self._slot_payload())
        return payload

    async def _loop(self) -> None:
        try:
            while True:
                now = self._now()
                self._next_run_at = self._compute_next_run_at(self._config, now)
                phase = self._due_phase(self._config, now)

                if phase is not None:
                    await self.run_now(trigger=phase, force=False)
                    continue

                self._wake_event.clear()
                timeout = None
                if self._next_run_at is not None:
                    timeout = max(
                        0.0,
                        (self._next_run_at - now).total_seconds(),
                    )

                try:
                    if timeout is None:
                        await self._wake_event.wait()
                    else:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise

    def _run_once(self, *, trigger: str, force: bool) -> AutoScheduleRunResult:
        now = self._now()
        config = self._config
        result = AutoScheduleRunResult(
            trigger=trigger,
            enabled=config.enabled,
            dry_run=self._settings.dry_run,
            started_at=now,
        )

        settings_error = self._settings.validation_error()
        if settings_error:
            result.errors.append(settings_error)
            return result.finish(False, settings_error)

        config_error = config.validate()
        if config_error:
            result.errors.append(config_error)
            return result.finish(False, config_error)

        automatic_phase = self._automatic_phase_for_trigger(trigger)
        if not force:
            if not config.enabled:
                return result.finish(True, "Automatic scheduling is disabled.")
            if config.is_expired(now):
                return result.finish(True, "Automatic scheduling configuration has expired.")
            due_phase = self._due_phase(config, now)
            if automatic_phase is None or due_phase != automatic_phase:
                return result.finish(True, "No automatic run is due right now.")

        if automatic_phase is not None:
            self._mark_attempt(automatic_phase, now)

        client: OrbitalClient | None = None
        created_client = False
        try:
            client, created_client, used_existing_session = self._acquire_client()
            result.used_existing_session = used_existing_session
            result.login_performed = created_client

            try:
                plan = self._build_plan(client, now, config)
            except OrbitalSessionExpired:
                if not used_existing_session or not self._settings.has_credentials:
                    raise

                client = self._login_client()
                created_client = True
                result.used_existing_session = False
                result.login_performed = True
                plan = self._build_plan(client, now, config)

            result.executed = True
            result = self._populate_counts(result, plan)

            if not plan.candidates:
                return result.finish(True, "No pending meals to schedule.")

            if self._settings.dry_run:
                return result.finish(
                    True,
                    f"Dry run completed with {result.candidates_count} candidate(s).",
                )

            current_client = client
            for item in plan.candidates:
                try:
                    current_client.agendar(item.dia, item.refeicao)
                    result.scheduled_count += 1
                except OrbitalSessionExpired as exc:
                    if result.used_existing_session and self._settings.has_credentials:
                        current_client = self._login_client()
                        client = current_client
                        created_client = True
                        result.used_existing_session = False
                        result.login_performed = True
                        try:
                            current_client.agendar(item.dia, item.refeicao)
                            result.scheduled_count += 1
                            continue
                        except OrbitalError as retry_exc:
                            self._record_error(result, item.dia, item.refeicao, retry_exc)
                            continue

                    self._record_error(result, item.dia, item.refeicao, exc)
                    break
                except OrbitalError as exc:
                    if is_already_scheduled_error(str(exc)):
                        result.already_scheduled_count += 1
                        continue
                    self._record_error(result, item.dia, item.refeicao, exc)

            if result.errors:
                return result.finish(
                    False,
                    (
                        f"Run completed with {result.scheduled_count} scheduled "
                        f"and {len(result.errors)} error(s)."
                    ),
                )

            return result.finish(
                True,
                f"Run completed with {result.scheduled_count} scheduled meal(s).",
            )
        except (AutoScheduleConfigError, OrbitalLoginError, OrbitalError) as exc:
            result.errors.append(str(exc))
            return result.finish(False, str(exc))
        except Exception as exc:
            self._logger.exception("Unexpected auto scheduler error")
            result.errors.append("Unexpected auto scheduler error.")
            result.last_error = str(exc)
            return result.finish(False, "Unexpected auto scheduler error.")
        finally:
            if created_client and client is not None:
                try:
                    client.logout()
                except Exception:
                    pass

    def _build_plan(
        self,
        client: OrbitalClient,
        now: datetime,
        config: AutoScheduleConfig,
    ):
        start, end = build_period_strings(now, self._settings.lookahead_days)
        cardapio = client.get_cardapio(start, end)
        agendamentos = client.get_agendamentos(start, end)
        return reconcile_auto_schedule(
            cardapio=cardapio,
            agendamentos=agendamentos,
            weekly_rules=config.weekly_rules or {},
            now=now,
            lookahead_days=self._settings.lookahead_days,
        )

    def _populate_counts(
        self,
        result: AutoScheduleRunResult,
        plan,
    ) -> AutoScheduleRunResult:
        result.candidates_count = len(plan.candidates)
        result.already_scheduled_count = plan.already_scheduled
        result.skipped_count = plan.skipped
        return result

    def _acquire_client(self) -> tuple[OrbitalClient, bool, bool]:
        active_session = self._session_manager.get_session_by_cpf(self._settings.cpf)
        if active_session:
            self._logger.info(
                "Auto scheduler reusing active session for CPF %s",
                self._settings.masked_cpf,
            )
            return active_session.orbital, False, True

        return self._login_client(), True, False

    def _login_client(self) -> OrbitalClient:
        if not self._settings.has_credentials:
            raise AutoScheduleConfigError(
                "Auto schedule credentials are not configured."
            )

        self._logger.info(
            "Auto scheduler logging into Orbital for CPF %s",
            self._settings.masked_cpf,
        )
        client = self._orbital_client_factory()
        client.login(self._settings.cpf, self._settings.password)
        return client

    def _record_error(
        self,
        result: AutoScheduleRunResult,
        dia: str,
        refeicao: str,
        exc: Exception,
    ) -> None:
        detail = f"{dia} - {refeicao}: {exc}"
        result.errors.append(detail)
        result.last_error = str(exc)

    def _mark_success(self, finished_at: datetime) -> None:
        self._config = self._config_store.save(
            replace(self._config, last_successful_run_at=finished_at)
        )

    def _mark_attempt(self, phase: AutoSchedulePhase, timestamp: datetime) -> None:
        if phase == "primary":
            self._config = self._config_store.save(
                replace(self._config, last_primary_attempt_at=timestamp)
            )
            return

        self._config = self._config_store.save(
            replace(self._config, last_fallback_attempt_at=timestamp)
        )

    def _slot_payload(self) -> dict[str, object]:
        primary_run_time = self._slot_time_string()
        return {
            "primary_day": PRIMARY_DAY,
            "primary_run_time": primary_run_time,
            "fallback_day": FALLBACK_DAY,
            "fallback_run_time": primary_run_time,
        }

    def _due_phase(
        self,
        config: AutoScheduleConfig,
        now: datetime,
    ) -> AutoSchedulePhase | None:
        if config.validate() is not None:
            return None
        if not config.enabled or config.is_expired(now):
            return None

        slot_time = self._slot_time()
        if slot_time is None:
            return None

        weekend_start = self._weekend_start(now)
        if now.weekday() == PRIMARY_WEEKDAY:
            if self._has_success_in_weekend(config, weekend_start):
                return None
            if self._has_primary_attempt_in_weekend(config, weekend_start):
                return None
            if now >= self._primary_datetime(weekend_start, slot_time, now.tzinfo):
                return "primary"
            return None

        if now.weekday() == FALLBACK_WEEKDAY:
            if self._has_success_in_weekend(config, weekend_start):
                return None
            if self._has_fallback_attempt_in_weekend(config, weekend_start):
                return None
            if now >= self._fallback_datetime(weekend_start, slot_time, now.tzinfo):
                return "fallback"

        return None

    def _compute_next_run_at(
        self,
        config: AutoScheduleConfig,
        now: datetime,
    ) -> datetime | None:
        if config.validate() is not None:
            return None
        if not config.enabled or config.is_expired(now):
            return None

        slot_time = self._slot_time()
        if slot_time is None:
            return None

        weekend_start = self._weekend_start(now)
        next_weekend_start = weekend_start + timedelta(days=7)

        if now.weekday() <= 4:
            return self._primary_datetime(next_weekend_start, slot_time, now.tzinfo)

        if now.weekday() == PRIMARY_WEEKDAY:
            if self._has_success_in_weekend(config, weekend_start):
                return self._primary_datetime(next_weekend_start, slot_time, now.tzinfo)

            primary_at = self._primary_datetime(weekend_start, slot_time, now.tzinfo)
            if not self._has_primary_attempt_in_weekend(config, weekend_start):
                return now if now >= primary_at else primary_at

            return self._fallback_datetime(weekend_start, slot_time, now.tzinfo)

        if self._has_success_in_weekend(config, weekend_start):
            return self._primary_datetime(next_weekend_start, slot_time, now.tzinfo)

        fallback_at = self._fallback_datetime(weekend_start, slot_time, now.tzinfo)
        if not self._has_fallback_attempt_in_weekend(config, weekend_start):
            return now if now >= fallback_at else fallback_at

        return self._primary_datetime(next_weekend_start, slot_time, now.tzinfo)

    def _automatic_phase_for_trigger(self, trigger: str) -> AutoSchedulePhase | None:
        if trigger == "primary":
            return "primary"
        if trigger == "fallback":
            return "fallback"
        return None

    def _slot_time_string(self) -> str | None:
        slot = self._slot_time()
        if slot is None:
            return None
        return f"{slot.hour:02d}:{slot.minute:02d}"

    def _slot_time(self) -> time | None:
        digits = "".join(ch for ch in self._settings.cpf if ch.isdigit())
        if not digits:
            return None

        digest = sha256(f"{SLOT_HASH_SALT}:{digits}".encode("utf-8")).digest()
        offset = int.from_bytes(digest[:8], byteorder="big") % SLOT_WINDOW_MINUTES
        total_minutes = SLOT_WINDOW_START.hour * 60 + SLOT_WINDOW_START.minute + offset
        return time(hour=total_minutes // 60, minute=total_minutes % 60)

    def _weekend_start(self, now: datetime) -> date:
        days_since_saturday = (now.weekday() - PRIMARY_WEEKDAY) % 7
        return now.date() - timedelta(days=days_since_saturday)

    def _primary_datetime(
        self,
        weekend_start: date,
        slot_time: time,
        tzinfo,
    ) -> datetime:
        return datetime.combine(weekend_start, slot_time, tzinfo=tzinfo)

    def _fallback_datetime(
        self,
        weekend_start: date,
        slot_time: time,
        tzinfo,
    ) -> datetime:
        return datetime.combine(weekend_start + timedelta(days=1), slot_time, tzinfo=tzinfo)

    def _has_success_in_weekend(
        self,
        config: AutoScheduleConfig,
        weekend_start: date,
    ) -> bool:
        return self._is_timestamp_in_weekend(config.last_successful_run_at, weekend_start)

    def _has_primary_attempt_in_weekend(
        self,
        config: AutoScheduleConfig,
        weekend_start: date,
    ) -> bool:
        return self._is_timestamp_on_day(config.last_primary_attempt_at, weekend_start)

    def _has_fallback_attempt_in_weekend(
        self,
        config: AutoScheduleConfig,
        weekend_start: date,
    ) -> bool:
        return self._is_timestamp_on_day(
            config.last_fallback_attempt_at,
            weekend_start + timedelta(days=1),
        )

    def _is_timestamp_in_weekend(
        self,
        value: datetime | None,
        weekend_start: date,
    ) -> bool:
        if value is None:
            return False

        local_value = local_now(self._settings.timezone_name, value)
        weekend_end = weekend_start + timedelta(days=1)
        return weekend_start <= local_value.date() <= weekend_end

    def _is_timestamp_on_day(
        self,
        value: datetime | None,
        target_day: date,
    ) -> bool:
        if value is None:
            return False
        return local_now(self._settings.timezone_name, value).date() == target_day

    def _now(self) -> datetime:
        return self._now_provider(self._settings.timezone_name)
