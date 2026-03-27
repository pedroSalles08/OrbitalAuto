from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
import logging

from auto_schedule_crypto import AutoScheduleCredentialCipher
from auto_schedule_domain import (
    build_period_strings,
    get_timezone,
    is_already_scheduled_error,
    local_now,
    reconcile_auto_schedule,
)
from auto_schedule_store import (
    AutoScheduleProfile,
    AutoScheduleProfileStore,
    calculate_active_until,
)
from auto_scheduler import (
    AutoScheduleConfigError,
    AutoSchedulePhase,
    AutoScheduleRunResult,
    FALLBACK_DAY,
    FALLBACK_WEEKDAY,
    PRIMARY_DAY,
    PRIMARY_WEEKDAY,
    late_sunday_fallback_warning,
    normalize_cpf_digits,
    slot_time_for_phase,
)
from orbital_client import OrbitalClient, OrbitalError, OrbitalLoginError, OrbitalSessionExpired
from session_manager import SessionManager


@dataclass(frozen=True)
class MultiUserAutoScheduleSettings:
    dry_run: bool
    timezone_name: str
    lookahead_days: int

    def validation_error(self) -> str | None:
        if self.lookahead_days < 1:
            return "AUTO_SCHEDULE_LOOKAHEAD_DAYS must be >= 1."

        try:
            get_timezone(self.timezone_name)
        except ValueError as exc:
            return str(exc)

        return None


class MultiUserAutoScheduler:
    def __init__(
        self,
        session_manager: SessionManager,
        settings: MultiUserAutoScheduleSettings,
        profile_store: AutoScheduleProfileStore,
        credential_cipher: AutoScheduleCredentialCipher | None = None,
        orbital_client_factory=OrbitalClient,
        now_provider=local_now,
    ) -> None:
        self._session_manager = session_manager
        self._settings = settings
        self._profile_store = profile_store
        self._credential_cipher = credential_cipher
        self._orbital_client_factory = orbital_client_factory
        self._now_provider = now_provider
        self._logger = logging.getLogger("multi_user_auto_scheduler")
        self._profiles = self._profile_store.load_all()
        self._last_runs: dict[str, AutoScheduleRunResult] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._running_cpfs: set[str] = set()
        self._loop_task: asyncio.Task | None = None
        self._wake_event = asyncio.Event()

    async def start(self) -> None:
        if self._loop_task:
            return

        self._logger.info(
            "Multi-user auto scheduler initialized (dry_run=%s timezone=%s store=%s)",
            self._settings.dry_run,
            self._settings.timezone_name,
            getattr(self._profile_store, "_path", "<memory>"),
        )
        self._loop_task = asyncio.create_task(
            self._loop(),
            name="multi-user-auto-scheduler",
        )

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

    async def run_now(
        self,
        cpf: str,
        trigger: str = "manual",
        *,
        force: bool = False,
    ) -> dict[str, object]:
        normalized_cpf = self._normalize_cpf(cpf)
        if not normalized_cpf:
            raise AutoScheduleConfigError("CPF invalido para auto schedule.")

        async with self._lock_for(normalized_cpf):
            self._running_cpfs.add(normalized_cpf)
            try:
                result = self._run_once(
                    normalized_cpf,
                    trigger=trigger,
                    force=force,
                )
                if (
                    result.success
                    and result.executed
                    and result.finished_at is not None
                ):
                    self._mark_success(normalized_cpf, result.finished_at)
                self._last_runs[normalized_cpf] = result
                self._wake_event.set()
                return result.to_payload()
            finally:
                self._running_cpfs.discard(normalized_cpf)

    def config_payload(self, cpf: str) -> dict[str, object]:
        normalized_cpf = self._normalize_cpf(cpf)
        profile = self._profile_for(normalized_cpf)
        payload = profile.to_payload()
        payload.update(self._slot_payload(normalized_cpf))
        return payload

    def status_payload(self, cpf: str) -> dict[str, object]:
        normalized_cpf = self._normalize_cpf(cpf)
        profile = self._profile_for(normalized_cpf)
        payload = profile.to_payload()
        payload.update(
            {
                "dry_run": self._settings.dry_run,
                "running": normalized_cpf in self._running_cpfs,
                "timezone": self._settings.timezone_name,
                "next_run_at": self._compute_next_run_at(profile, self._now()),
                "last_run": (
                    self._last_runs[normalized_cpf].to_payload()
                    if normalized_cpf in self._last_runs
                    else None
                ),
            }
        )
        payload.update(self._slot_payload(normalized_cpf))
        return payload

    def save_config(
        self,
        cpf: str,
        *,
        enabled: bool,
        weekly_rules: dict[str, list[str]],
        duration_mode: str,
        orbital_password: str | None = None,
        clear_saved_credentials: bool = False,
    ) -> dict[str, object]:
        normalized_cpf = self._normalize_cpf(cpf)
        if not normalized_cpf:
            raise AutoScheduleConfigError("CPF invalido para auto schedule.")

        now = self._now()
        current = self._profile_for(normalized_cpf)
        next_encrypted_password = current.encrypted_password
        next_credentials_updated_at = current.credentials_updated_at
        normalized_password = (orbital_password or "").strip()

        if clear_saved_credentials and not normalized_password:
            next_encrypted_password = None
            next_credentials_updated_at = None

        if normalized_password:
            next_encrypted_password = self._encrypt_password(normalized_password)
            next_credentials_updated_at = now

        if enabled and not next_encrypted_password:
            raise AutoScheduleConfigError(
                "Informe a senha do Orbital para ativar a automacao."
            )

        candidate = AutoScheduleProfile(
            cpf=normalized_cpf,
            enabled=enabled,
            weekly_rules=weekly_rules,
            duration_mode=duration_mode,
            active_until=calculate_active_until(duration_mode, now),
            updated_at=now,
            last_successful_run_at=current.last_successful_run_at,
            last_primary_attempt_at=current.last_primary_attempt_at,
            last_fallback_attempt_at=current.last_fallback_attempt_at,
            encrypted_password=next_encrypted_password,
            credentials_updated_at=next_credentials_updated_at,
        ).normalized()

        validation_error = candidate.validate()
        if validation_error:
            raise AutoScheduleConfigError(validation_error)

        saved = self._save_profile(candidate)
        self._wake_event.set()
        payload = saved.to_payload()
        payload.update(self._slot_payload(normalized_cpf))
        return payload

    async def _loop(self) -> None:
        try:
            while True:
                now = self._now()
                due_profiles = self._due_profiles(now)

                if due_profiles:
                    for _, cpf, phase in due_profiles:
                        await self.run_now(cpf, trigger=phase, force=False)
                    continue

                self._wake_event.clear()
                timeout = self._next_timeout(now)
                try:
                    if timeout is None:
                        await self._wake_event.wait()
                    else:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise

    def _due_profiles(
        self,
        now: datetime,
    ) -> list[tuple[datetime, str, AutoSchedulePhase]]:
        due: list[tuple[datetime, str, AutoSchedulePhase]] = []
        for cpf, profile in self._profiles.items():
            phase = self._due_phase(profile, now)
            if phase is None:
                continue
            next_run_at = self._compute_next_run_at(profile, now) or now
            due.append((next_run_at, cpf, phase))
        return sorted(due, key=lambda item: (item[0], item[1]))

    def _next_timeout(self, now: datetime) -> float | None:
        next_run_at: datetime | None = None
        for profile in self._profiles.values():
            candidate = self._compute_next_run_at(profile, now)
            if candidate is None:
                continue
            if next_run_at is None or candidate < next_run_at:
                next_run_at = candidate

        if next_run_at is None:
            return None

        return max(0.0, (next_run_at - now).total_seconds())

    def _run_once(
        self,
        cpf: str,
        *,
        trigger: str,
        force: bool,
    ) -> AutoScheduleRunResult:
        now = self._now()
        profile = self._profile_for(cpf)
        result = AutoScheduleRunResult(
            trigger=trigger,
            enabled=profile.enabled,
            dry_run=self._settings.dry_run,
            started_at=now,
        )
        fallback_warning = late_sunday_fallback_warning(trigger, now)
        if fallback_warning:
            self._logger.warning("%s CPF %s", fallback_warning, self._mask_cpf(cpf))

        settings_error = self._settings.validation_error()
        if settings_error:
            result.errors.append(settings_error)
            return result.finish(False, settings_error)

        config_error = profile.validate()
        if config_error:
            result.errors.append(config_error)
            return result.finish(False, config_error)

        automatic_phase = self._automatic_phase_for_trigger(trigger)
        if not force:
            if not profile.enabled:
                return result.finish(True, "Automatic scheduling is disabled.")
            if profile.is_expired(now):
                return result.finish(
                    True,
                    "Automatic scheduling configuration has expired.",
                )
            due_phase = self._due_phase(profile, now)
            if automatic_phase is None or due_phase != automatic_phase:
                return result.finish(True, "No automatic run is due right now.")

        if automatic_phase is not None:
            self._mark_attempt(cpf, automatic_phase, now)
            profile = self._profile_for(cpf)

        client: OrbitalClient | None = None
        created_client = False
        try:
            client, created_client, used_existing_session = self._acquire_client(
                cpf,
                profile,
            )
            result.used_existing_session = used_existing_session
            result.login_performed = created_client

            try:
                plan = self._build_plan(client, now, profile)
            except OrbitalSessionExpired:
                if not used_existing_session or not profile.has_credentials:
                    raise

                client = self._login_client(cpf, profile)
                created_client = True
                result.used_existing_session = False
                result.login_performed = True
                plan = self._build_plan(client, now, profile)

            result.executed = True
            result = self._populate_counts(result, plan)

            if not plan.candidates:
                return result.finish(
                    True,
                    self._append_warning(
                        "No pending meals to schedule.",
                        fallback_warning,
                    ),
                )

            if self._settings.dry_run:
                return result.finish(
                    True,
                    self._append_warning(
                        f"Dry run completed with {result.candidates_count} candidate(s).",
                        fallback_warning,
                    ),
                )

            current_client = client
            for item in plan.candidates:
                try:
                    current_client.agendar(item.dia, item.refeicao)
                    result.scheduled_count += 1
                except OrbitalSessionExpired as exc:
                    if result.used_existing_session and profile.has_credentials:
                        current_client = self._login_client(cpf, profile)
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
                    self._append_warning(
                        (
                            f"Run completed with {result.scheduled_count} scheduled "
                            f"and {len(result.errors)} error(s)."
                        ),
                        fallback_warning,
                    ),
                )

            return result.finish(
                True,
                self._append_warning(
                    f"Run completed with {result.scheduled_count} scheduled meal(s).",
                    fallback_warning,
                ),
            )
        except (AutoScheduleConfigError, OrbitalLoginError, OrbitalError) as exc:
            result.errors.append(str(exc))
            return result.finish(False, str(exc))
        except Exception as exc:
            self._logger.exception("Unexpected multi-user auto scheduler error")
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
        profile: AutoScheduleProfile,
    ):
        start, end = build_period_strings(now, self._settings.lookahead_days)
        cardapio = client.get_cardapio(start, end)
        agendamentos = client.get_agendamentos(start, end)
        return reconcile_auto_schedule(
            cardapio=cardapio,
            agendamentos=agendamentos,
            weekly_rules=profile.weekly_rules or {},
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

    def _acquire_client(
        self,
        cpf: str,
        profile: AutoScheduleProfile,
    ) -> tuple[OrbitalClient, bool, bool]:
        active_session = self._session_manager.get_session_by_cpf(cpf)
        if active_session:
            self._logger.info(
                "Auto scheduler reusing active session for CPF %s",
                self._mask_cpf(cpf),
            )
            return active_session.orbital, False, True

        return self._login_client(cpf, profile), True, False

    def _login_client(
        self,
        cpf: str,
        profile: AutoScheduleProfile,
    ) -> OrbitalClient:
        if not profile.has_credentials:
            raise AutoScheduleConfigError(
                "Auto schedule credentials are not configured."
            )

        if self._credential_cipher is None:
            raise AutoScheduleConfigError(
                "AUTO_SCHEDULE_ENCRYPTION_KEY is not configured."
            )

        password = self._credential_cipher.decrypt(profile.encrypted_password or "")
        self._logger.info(
            "Auto scheduler logging into Orbital for CPF %s",
            self._mask_cpf(cpf),
        )
        client = self._orbital_client_factory()
        client.login(cpf, password)
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

    def _mark_success(self, cpf: str, finished_at: datetime) -> None:
        profile = self._profile_for(cpf)
        self._save_profile(
            replace(profile, last_successful_run_at=finished_at).normalized()
        )

    def _mark_attempt(
        self,
        cpf: str,
        phase: AutoSchedulePhase,
        timestamp: datetime,
    ) -> None:
        profile = self._profile_for(cpf)
        if phase == "primary":
            updated = replace(profile, last_primary_attempt_at=timestamp)
        else:
            updated = replace(profile, last_fallback_attempt_at=timestamp)
        self._save_profile(updated.normalized())

    def _slot_payload(self, cpf: str) -> dict[str, object]:
        primary_run_time = self._slot_time_string(cpf, "primary")
        fallback_run_time = self._slot_time_string(cpf, "fallback")
        return {
            "primary_day": PRIMARY_DAY,
            "primary_run_time": primary_run_time,
            "fallback_day": FALLBACK_DAY,
            "fallback_run_time": fallback_run_time,
        }

    def _due_phase(
        self,
        profile: AutoScheduleProfile,
        now: datetime,
    ) -> AutoSchedulePhase | None:
        if profile.validate() is not None:
            return None
        if not profile.enabled or profile.is_expired(now):
            return None
        if not profile.has_credentials:
            return None

        primary_slot_time = self._slot_time(profile.cpf, "primary")
        fallback_slot_time = self._slot_time(profile.cpf, "fallback")
        if primary_slot_time is None or fallback_slot_time is None:
            return None

        weekend_start = self._weekend_start(now)
        if now.weekday() == PRIMARY_WEEKDAY:
            if self._has_success_in_weekend(profile, weekend_start):
                return None
            if self._has_primary_attempt_in_weekend(profile, weekend_start):
                return None
            if now >= self._primary_datetime(
                weekend_start,
                primary_slot_time,
                now.tzinfo,
            ):
                return "primary"
            return None

        if now.weekday() == FALLBACK_WEEKDAY:
            if self._has_success_in_weekend(profile, weekend_start):
                return None
            if self._has_fallback_attempt_in_weekend(profile, weekend_start):
                return None
            if now >= self._fallback_datetime(
                weekend_start,
                fallback_slot_time,
                now.tzinfo,
            ):
                return "fallback"

        return None

    def _compute_next_run_at(
        self,
        profile: AutoScheduleProfile,
        now: datetime,
    ) -> datetime | None:
        if profile.validate() is not None:
            return None
        if not profile.enabled or profile.is_expired(now):
            return None
        if not profile.has_credentials:
            return None

        primary_slot_time = self._slot_time(profile.cpf, "primary")
        fallback_slot_time = self._slot_time(profile.cpf, "fallback")
        if primary_slot_time is None or fallback_slot_time is None:
            return None

        weekend_start = self._weekend_start(now)
        next_weekend_start = weekend_start + timedelta(days=7)

        if now.weekday() <= 4:
            return self._primary_datetime(
                next_weekend_start,
                primary_slot_time,
                now.tzinfo,
            )

        if now.weekday() == PRIMARY_WEEKDAY:
            if self._has_success_in_weekend(profile, weekend_start):
                return self._primary_datetime(
                    next_weekend_start,
                    primary_slot_time,
                    now.tzinfo,
                )

            primary_at = self._primary_datetime(
                weekend_start,
                primary_slot_time,
                now.tzinfo,
            )
            if not self._has_primary_attempt_in_weekend(profile, weekend_start):
                return now if now >= primary_at else primary_at

            return self._fallback_datetime(
                weekend_start,
                fallback_slot_time,
                now.tzinfo,
            )

        if self._has_success_in_weekend(profile, weekend_start):
            return self._primary_datetime(
                next_weekend_start,
                primary_slot_time,
                now.tzinfo,
            )

        fallback_at = self._fallback_datetime(
            weekend_start,
            fallback_slot_time,
            now.tzinfo,
        )
        if not self._has_fallback_attempt_in_weekend(profile, weekend_start):
            return now if now >= fallback_at else fallback_at

        return self._primary_datetime(
            next_weekend_start,
            primary_slot_time,
            now.tzinfo,
        )

    def _automatic_phase_for_trigger(self, trigger: str) -> AutoSchedulePhase | None:
        if trigger == "primary":
            return "primary"
        if trigger == "fallback":
            return "fallback"
        return None

    def _slot_time_string(self, cpf: str, phase: AutoSchedulePhase) -> str | None:
        slot = self._slot_time(cpf, phase)
        if slot is None:
            return None
        return f"{slot.hour:02d}:{slot.minute:02d}"

    def _slot_time(self, cpf: str, phase: AutoSchedulePhase) -> time | None:
        return slot_time_for_phase(cpf, phase)

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
        return datetime.combine(
            weekend_start + timedelta(days=1),
            slot_time,
            tzinfo=tzinfo,
        )

    def _has_success_in_weekend(
        self,
        profile: AutoScheduleProfile,
        weekend_start: date,
    ) -> bool:
        return self._is_timestamp_in_weekend(
            profile.last_successful_run_at,
            weekend_start,
        )

    def _has_primary_attempt_in_weekend(
        self,
        profile: AutoScheduleProfile,
        weekend_start: date,
    ) -> bool:
        return self._is_timestamp_on_day(profile.last_primary_attempt_at, weekend_start)

    def _has_fallback_attempt_in_weekend(
        self,
        profile: AutoScheduleProfile,
        weekend_start: date,
    ) -> bool:
        return self._is_timestamp_on_day(
            profile.last_fallback_attempt_at,
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

    def _save_profile(self, profile: AutoScheduleProfile) -> AutoScheduleProfile:
        saved = self._profile_store.save(profile)
        self._profiles[saved.cpf] = saved
        return saved

    def _profile_for(self, cpf: str) -> AutoScheduleProfile:
        normalized_cpf = self._normalize_cpf(cpf)
        existing = self._profiles.get(normalized_cpf)
        if existing is not None:
            return existing
        return AutoScheduleProfile.empty(normalized_cpf)

    def _lock_for(self, cpf: str) -> asyncio.Lock:
        normalized_cpf = self._normalize_cpf(cpf)
        if normalized_cpf not in self._locks:
            self._locks[normalized_cpf] = asyncio.Lock()
        return self._locks[normalized_cpf]

    def _encrypt_password(self, password: str) -> str:
        if self._credential_cipher is None:
            raise AutoScheduleConfigError(
                "AUTO_SCHEDULE_ENCRYPTION_KEY is not configured."
            )
        return self._credential_cipher.encrypt(password)

    def _now(self) -> datetime:
        return self._now_provider(self._settings.timezone_name)

    def _normalize_cpf(self, cpf: str) -> str:
        return normalize_cpf_digits(cpf)

    def _mask_cpf(self, cpf: str) -> str:
        digits = self._normalize_cpf(cpf)
        if len(digits) < 3:
            return "***"
        return f"{digits[:3]}***"

    def _append_warning(self, message: str, warning: str | None) -> str:
        if not warning:
            return message
        return f"{message} Aviso: {warning}"
