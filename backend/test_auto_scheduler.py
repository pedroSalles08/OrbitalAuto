from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from datetime import datetime
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

from auto_schedule_crypto import AutoScheduleCredentialCipher
from auto_schedule_domain import WEEKDAY_CODES, can_schedule, reconcile_auto_schedule
from auto_schedule_store import (
    AutoScheduleConfig,
    AutoScheduleConfigStore,
    AutoScheduleProfile,
    AutoScheduleProfileStore,
)
from auto_scheduler import AutoScheduleConfigError, AutoScheduler, AutoScheduleSettings
from multi_user_auto_scheduler import (
    MultiUserAutoScheduleSettings,
    MultiUserAutoScheduler,
)


TZ = ZoneInfo("America/Sao_Paulo")


def make_weekly_rules(**overrides: list[str]) -> dict[str, tuple[str, ...]]:
    rules = {weekday: tuple() for weekday in WEEKDAY_CODES}
    for weekday, meals in overrides.items():
        rules[weekday] = tuple(meals)
    return rules


class FakeOrbitalClient:
    def __init__(self, *, cardapio, agendamentos) -> None:
        self._cardapio = cardapio
        self._agendamentos = agendamentos
        self.login_calls: list[tuple[str, str]] = []
        self.period_calls: list[tuple[str, str]] = []
        self.agendar_calls: list[tuple[str, str]] = []
        self.logout_calls = 0

    def login(self, cpf: str, senha: str) -> str:
        self.login_calls.append((cpf, senha))
        return "Tester"

    def get_cardapio(self, inicio: str | None = None, fim: str | None = None):
        self.period_calls.append((inicio or "", fim or ""))
        return self._cardapio

    def get_agendamentos(self, inicio: str | None = None, fim: str | None = None):
        self.period_calls.append((inicio or "", fim or ""))
        return self._agendamentos

    def agendar(self, dia: str, refeicao: str):
        self.agendar_calls.append((dia, refeicao))
        return {"success": True}

    def logout(self) -> None:
        self.logout_calls += 1


class FakeSessionManager:
    def __init__(self, session=None, sessions: dict[str, object] | None = None) -> None:
        self._session = session
        self._sessions = sessions or {}

    def get_session_by_cpf(self, cpf: str):
        if cpf in self._sessions:
            return self._sessions[cpf]
        return self._session


class FakeConfigStore:
    def __init__(self, config: AutoScheduleConfig) -> None:
        self._config = config

    def load(self) -> AutoScheduleConfig:
        return self._config

    def save(self, config: AutoScheduleConfig) -> AutoScheduleConfig:
        self._config = config
        return config


class AutoScheduleDomainTests(unittest.TestCase):
    def test_can_schedule_respects_previous_day_deadline(self):
        before_deadline = datetime(2026, 3, 22, 16, 59, tzinfo=TZ)
        after_deadline = datetime(2026, 3, 22, 17, 0, tzinfo=TZ)

        self.assertEqual(can_schedule("2026-03-23", before_deadline), (True, "OK"))
        self.assertEqual(
            can_schedule("2026-03-23", after_deadline),
            (False, "Prazo expirado (agendamento ate 17h do dia anterior)"),
        )

    def test_reconcile_auto_schedule_respects_specific_day_and_meal_pairs(self):
        now = datetime(2026, 3, 21, 10, 0, tzinfo=TZ)
        cardapio = [
            {"data": "2026-03-23", "refeicoes": [{"tipo": "AL"}, {"tipo": "JA"}]},
            {"data": "2026-03-26", "refeicoes": [{"tipo": "AL"}, {"tipo": "JA"}]},
        ]

        plan = reconcile_auto_schedule(
            cardapio=cardapio,
            agendamentos=[{"dia": "2026-03-23", "tipo_codigo": "AL"}],
            weekly_rules=make_weekly_rules(MON=["AL"], THU=["JA"]),
            now=now,
            lookahead_days=7,
        )

        self.assertEqual(
            [(item.dia, item.refeicao) for item in plan.candidates],
            [("2026-03-26", "JA")],
        )
        self.assertEqual(plan.already_scheduled, 1)


class AutoScheduleStoreTests(unittest.TestCase):
    def _make_tmp_dir(self, name: str) -> Path:
        tmp_root = Path(__file__).resolve().parent / ".tmp_test_data" / name
        shutil.rmtree(tmp_root, ignore_errors=True)
        tmp_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmp_root, ignore_errors=True))
        return tmp_root

    def test_legacy_meals_are_migrated_to_all_weekdays(self):
        tmp_root = self._make_tmp_dir("legacy_auto_schedule")
        config_path = tmp_root / "legacy_auto_schedule_config.json"
        config_path.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "meals": ["AL", "JA"],
                    "duration_mode": "30d",
                }
            ),
            encoding="utf-8",
        )

        try:
            store = AutoScheduleConfigStore(config_path)
            loaded = store.load()

            for weekday in WEEKDAY_CODES:
                self.assertEqual(loaded.weekly_rules[weekday], ("AL", "JA"))
        finally:
            config_path.unlink(missing_ok=True)

    def test_enabled_config_requires_at_least_one_rule(self):
        config = AutoScheduleConfig(
            enabled=True,
            weekly_rules=make_weekly_rules(),
            duration_mode="30d",
        ).normalized()

        self.assertEqual(
            config.validate(),
            "Selecione ao menos uma combinacao de dia e refeicao para ativar a automacao.",
        )

    def test_profile_store_round_trips_profiles_by_cpf(self):
        tmp_root = self._make_tmp_dir("profile_round_trip")
        store = AutoScheduleProfileStore(tmp_root / "profiles.json")
        first = store.save(
            AutoScheduleProfile(
                cpf="123.456.789-01",
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                encrypted_password="enc-1",
                credentials_updated_at=datetime(2026, 3, 22, 9, 0, tzinfo=TZ),
            )
        )
        second = store.save(
            AutoScheduleProfile(
                cpf="999.999.999-99",
                enabled=False,
                weekly_rules=make_weekly_rules(THU=["JA"]),
                duration_mode="90d",
                encrypted_password="enc-2",
            )
        )

        profiles = store.load_all()

        self.assertEqual(first.cpf, "12345678901")
        self.assertEqual(second.cpf, "99999999999")
        self.assertEqual(sorted(profiles.keys()), ["12345678901", "99999999999"])
        self.assertEqual(profiles["12345678901"].weekly_rules["MON"], ("AL",))
        self.assertEqual(profiles["99999999999"].weekly_rules["THU"], ("JA",))

    def test_profile_store_keeps_credentials_metadata(self):
        tmp_root = self._make_tmp_dir("profile_credentials")
        store = AutoScheduleProfileStore(tmp_root / "profiles.json")
        saved = store.save(
            AutoScheduleProfile(
                cpf="12345678901",
                encrypted_password="encrypted-value",
                credentials_updated_at=datetime(2026, 3, 22, 9, 30, tzinfo=TZ),
            )
        )

        loaded = store.load("12345678901")

        self.assertEqual(saved.encrypted_password, "encrypted-value")
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.has_credentials)
        self.assertEqual(loaded.credentials_updated_at, saved.credentials_updated_at)


class AutoSchedulerTests(unittest.IsolatedAsyncioTestCase):
    def _make_store(self, config: AutoScheduleConfig) -> FakeConfigStore:
        return FakeConfigStore(config)

    def _make_scheduler(
        self,
        *,
        now: datetime,
        config: AutoScheduleConfig | None = None,
        client: FakeOrbitalClient | None = None,
        session=None,
        cpf: str = "12345678901",
    ) -> tuple[AutoScheduler, FakeOrbitalClient, FakeConfigStore]:
        fake_client = client or FakeOrbitalClient(
            cardapio=[
                {"data": "2026-03-23", "refeicoes": [{"tipo": "AL"}]},
            ],
            agendamentos=[],
        )
        store = self._make_store(
            config
            or AutoScheduleConfig(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
            )
        )
        scheduler = AutoScheduler(
            session_manager=FakeSessionManager(session=session),
            settings=AutoScheduleSettings(
                dry_run=True,
                timezone_name="America/Sao_Paulo",
                lookahead_days=7,
                cpf=cpf,
                password="secret",
            ),
            config_store=store,
            orbital_client_factory=lambda: fake_client,
            now_provider=lambda _: now,
        )
        return scheduler, fake_client, store

    async def test_manual_force_run_executes_in_dry_run_mode(self):
        scheduler, client, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
            config=AutoScheduleConfig(
                enabled=False,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
            ),
        )

        payload = await scheduler.run_now(trigger="manual", force=True)

        self.assertTrue(payload["success"])
        self.assertFalse(payload["enabled"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["login_performed"])
        self.assertEqual(payload["candidates_count"], 1)
        self.assertEqual(payload["scheduled_count"], 0)
        self.assertEqual(client.login_calls, [("12345678901", "secret")])
        self.assertEqual(client.agendar_calls, [])
        self.assertEqual(client.logout_calls, 1)
        self.assertIsNotNone(scheduler.status_payload()["last_successful_run_at"])

    async def test_scheduler_reuses_active_session_when_available(self):
        active_client = FakeOrbitalClient(
            cardapio=[{"data": "2026-03-23", "refeicoes": [{"tipo": "AL"}]}],
            agendamentos=[],
        )
        session = SimpleNamespace(orbital=active_client)
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
            client=active_client,
            session=session,
        )

        payload = await scheduler.run_now(trigger="manual", force=True)

        self.assertTrue(payload["success"])
        self.assertTrue(payload["used_existing_session"])
        self.assertFalse(payload["login_performed"])
        self.assertEqual(active_client.login_calls, [])
        self.assertEqual(active_client.logout_calls, 0)

    def test_same_cpf_always_generates_same_weekend_slot(self):
        scheduler_a, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 20, 9, 0, tzinfo=TZ),
            cpf="12345678901",
        )
        scheduler_b, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
            cpf="12345678901",
        )

        self.assertEqual(
            scheduler_a.status_payload()["primary_run_time"],
            scheduler_b.status_payload()["primary_run_time"],
        )
        self.assertEqual(
            scheduler_a.status_payload()["fallback_run_time"],
            scheduler_b.status_payload()["fallback_run_time"],
        )

    def test_primary_and_fallback_slots_are_independent_and_fallback_stays_before_noon(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 20, 9, 0, tzinfo=TZ),
            cpf="12345678901",
        )

        status = scheduler.status_payload()

        self.assertEqual(status["primary_run_time"], "18:51")
        self.assertEqual(status["fallback_run_time"], "06:23")
        self.assertLess(int(status["fallback_run_time"].split(":")[0]), 12)

    def test_before_weekend_slot_next_run_points_to_saturday(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 7, 0, tzinfo=TZ),
        )

        status = scheduler.status_payload()

        self.assertEqual(status["next_run_at"].date().isoformat(), "2026-03-21")
        self.assertEqual(
            status["next_run_at"].strftime("%H:%M"),
            status["primary_run_time"],
        )

    async def test_startup_runs_primary_once_when_saturday_slot_is_missed(self):
        scheduler, _, store = self._make_scheduler(
            now=datetime(2026, 3, 21, 23, 0, tzinfo=TZ),
        )

        await scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()

        status = scheduler.status_payload()
        self.assertEqual(status["last_run"]["trigger"], "primary")
        self.assertTrue(status["last_run"]["success"])
        self.assertEqual(
            store.load().last_primary_attempt_at.date().isoformat(),
            "2026-03-21",
        )

    async def test_startup_runs_fallback_on_sunday_without_success(self):
        scheduler, _, store = self._make_scheduler(
            now=datetime(2026, 3, 22, 16, 30, tzinfo=TZ),
            config=AutoScheduleConfig(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
                last_primary_attempt_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
            ),
        )

        await scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()

        status = scheduler.status_payload()
        self.assertEqual(status["last_run"]["trigger"], "fallback")
        self.assertTrue(status["last_run"]["success"])
        self.assertEqual(
            store.load().last_fallback_attempt_at.date().isoformat(),
            "2026-03-22",
        )

    async def test_late_sunday_fallback_appends_deadline_warning(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 22, 18, 0, tzinfo=TZ),
            config=AutoScheduleConfig(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
                last_primary_attempt_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
            ),
        )

        await scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()

        status = scheduler.status_payload()
        self.assertIn("apos 17h", status["last_run"]["message"])
        self.assertEqual(status["last_run"]["trigger"], "fallback")

    def test_success_on_saturday_suppresses_sunday_fallback(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 22, 23, 0, tzinfo=TZ),
            config=AutoScheduleConfig(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
                last_successful_run_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
                last_primary_attempt_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
            ),
        )

        status = scheduler.status_payload()

        self.assertEqual(status["next_run_at"].date().isoformat(), "2026-03-28")

    def test_monday_does_not_retry_missed_weekend(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 23, 9, 0, tzinfo=TZ),
            config=AutoScheduleConfig(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
                last_primary_attempt_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
                last_fallback_attempt_at=datetime(2026, 3, 22, 12, 0, tzinfo=TZ),
            ),
        )

        status = scheduler.status_payload()

        self.assertEqual(status["next_run_at"].date().isoformat(), "2026-03-28")

    def test_primary_attempt_is_not_duplicated_after_restart(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 23, 0, tzinfo=TZ),
            config=AutoScheduleConfig(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
                active_until=datetime(2026, 4, 21, 9, 0, tzinfo=TZ).date(),
                last_primary_attempt_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
            ),
        )

        status = scheduler.status_payload()

        self.assertEqual(status["next_run_at"].date().isoformat(), "2026-03-22")
        self.assertEqual(status["next_run_at"].strftime("%H:%M"), status["fallback_run_time"])


class MultiUserAutoSchedulerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        tmp_root = Path(__file__).resolve().parent / ".tmp_test_data"
        tmp_root.mkdir(parents=True, exist_ok=True)
        self._tmp_dir = tmp_root / f"multi_user_{self._testMethodName}"
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self._tmp_dir, ignore_errors=True))

    def _make_scheduler(
        self,
        *,
        now: datetime,
        client: FakeOrbitalClient | None = None,
        sessions: dict[str, object] | None = None,
        store: AutoScheduleProfileStore | None = None,
    ) -> tuple[MultiUserAutoScheduler, FakeOrbitalClient, AutoScheduleProfileStore]:
        fake_client = client or FakeOrbitalClient(
            cardapio=[
                {"data": "2026-03-23", "refeicoes": [{"tipo": "AL"}]},
            ],
            agendamentos=[],
        )
        profile_store = store or AutoScheduleProfileStore(
            self._tmp_dir / "profiles.json"
        )
        cipher = AutoScheduleCredentialCipher(Fernet.generate_key().decode("utf-8"))
        scheduler = MultiUserAutoScheduler(
            session_manager=FakeSessionManager(sessions=sessions),
            settings=MultiUserAutoScheduleSettings(
                dry_run=True,
                timezone_name="America/Sao_Paulo",
                lookahead_days=7,
            ),
            profile_store=profile_store,
            credential_cipher=cipher,
            orbital_client_factory=lambda: fake_client,
            now_provider=lambda _: now,
        )
        return scheduler, fake_client, profile_store

    def test_save_config_requires_password_when_enabling(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
        )

        with self.assertRaises(AutoScheduleConfigError):
            scheduler.save_config(
                "12345678901",
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"]),
                duration_mode="30d",
            )

    def test_save_config_persists_encrypted_credentials_per_user(self):
        scheduler, _, store = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
        )

        first = scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="first-secret",
        )
        second = scheduler.save_config(
            "99999999999",
            enabled=True,
            weekly_rules=make_weekly_rules(THU=["JA"]),
            duration_mode="90d",
            orbital_password="second-secret",
        )

        profiles = store.load_all()

        self.assertTrue(first["has_credentials"])
        self.assertTrue(second["has_credentials"])
        self.assertNotEqual(
            profiles["12345678901"].encrypted_password,
            profiles["99999999999"].encrypted_password,
        )
        self.assertEqual(profiles["12345678901"].weekly_rules["MON"], ("AL",))
        self.assertEqual(profiles["99999999999"].weekly_rules["THU"], ("JA",))

    async def test_manual_run_logs_in_with_saved_credentials_for_current_user(self):
        scheduler, client, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )

        payload = await scheduler.run_now("12345678901", trigger="manual", force=True)

        self.assertTrue(payload["success"])
        self.assertTrue(payload["login_performed"])
        self.assertEqual(client.login_calls, [("12345678901", "secret-123")])
        self.assertIsNotNone(
            scheduler.status_payload("12345678901")["last_successful_run_at"]
        )

    async def test_manual_run_reuses_active_session_for_matching_cpf(self):
        active_client = FakeOrbitalClient(
            cardapio=[{"data": "2026-03-23", "refeicoes": [{"tipo": "AL"}]}],
            agendamentos=[],
        )
        session = SimpleNamespace(orbital=active_client)
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
            client=active_client,
            sessions={"12345678901": session},
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )

        payload = await scheduler.run_now("12345678901", trigger="manual", force=True)

        self.assertTrue(payload["used_existing_session"])
        self.assertFalse(payload["login_performed"])
        self.assertEqual(active_client.login_calls, [])

    async def test_restart_preserves_profiles_and_credentials(self):
        store_path = self._tmp_dir / "profiles.json"
        store = AutoScheduleProfileStore(store_path)
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
            store=store,
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )

        restarted_scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
            store=AutoScheduleProfileStore(store_path),
        )
        status = restarted_scheduler.status_payload("12345678901")

        self.assertTrue(status["has_credentials"])
        self.assertTrue(status["enabled"])
        self.assertEqual(status["weekly_rules"]["MON"], ["AL"])
        self.assertIsNotNone(status["credentials_updated_at"])

    def test_clear_saved_credentials_removes_stored_secret(self):
        scheduler, _, store = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )

        response = scheduler.save_config(
            "12345678901",
            enabled=False,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            clear_saved_credentials=True,
        )
        profile = store.load("12345678901")

        self.assertFalse(response["has_credentials"])
        self.assertIsNotNone(profile)
        self.assertFalse(profile.has_credentials)
        self.assertIsNone(profile.credentials_updated_at)

    async def test_running_one_user_does_not_change_other_profile(self):
        scheduler, _, store = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )
        scheduler.save_config(
            "99999999999",
            enabled=True,
            weekly_rules=make_weekly_rules(THU=["JA"]),
            duration_mode="90d",
            orbital_password="secret-999",
        )

        await scheduler.run_now("12345678901", trigger="manual", force=True)
        second_profile = store.load("99999999999")

        self.assertIsNotNone(second_profile)
        self.assertIsNone(second_profile.last_successful_run_at)
        self.assertEqual(second_profile.weekly_rules["THU"], ("JA",))

    def test_status_payload_exposes_independent_weekend_slots(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 21, 9, 0, tzinfo=TZ),
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )

        status = scheduler.status_payload("12345678901")

        self.assertEqual(status["primary_run_time"], "18:51")
        self.assertEqual(status["fallback_run_time"], "06:23")
        self.assertLess(int(status["fallback_run_time"].split(":")[0]), 12)

    async def test_multi_user_startup_runs_fallback_on_sunday_afternoon(self):
        scheduler, _, _ = self._make_scheduler(
            now=datetime(2026, 3, 22, 16, 30, tzinfo=TZ),
        )
        scheduler.save_config(
            "12345678901",
            enabled=True,
            weekly_rules=make_weekly_rules(MON=["AL"]),
            duration_mode="30d",
            orbital_password="secret-123",
        )
        profile = scheduler._profile_for("12345678901")
        scheduler._save_profile(
            replace(
                profile,
                last_primary_attempt_at=datetime(2026, 3, 21, 12, 0, tzinfo=TZ),
            ).normalized()
        )

        await scheduler.start()
        await asyncio.sleep(0.05)
        await scheduler.stop()

        status = scheduler.status_payload("12345678901")
        self.assertEqual(status["last_run"]["trigger"], "fallback")


if __name__ == "__main__":
    unittest.main()
