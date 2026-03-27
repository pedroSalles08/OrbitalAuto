from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from starlette.requests import Request

import app as app_module
from models import AutoScheduleConfigRequest


TZ = ZoneInfo("America/Sao_Paulo")


def make_weekly_rules(**overrides: list[str]) -> dict[str, list[str]]:
    rules = {
        "MON": [],
        "TUE": [],
        "WED": [],
        "THU": [],
        "FRI": [],
        "SAT": [],
        "SUN": [],
    }
    for weekday, meals in overrides.items():
        rules[weekday] = list(meals)
    return rules


class AutoScheduleApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._original_config_payload = app_module.auto_scheduler.config_payload
        self._original_save_config = app_module.auto_scheduler.save_config
        self._original_status_payload = app_module.auto_scheduler.status_payload
        self._original_run_now = app_module.auto_scheduler.run_now

    def tearDown(self) -> None:
        app_module.auto_scheduler.config_payload = self._original_config_payload
        app_module.auto_scheduler.save_config = self._original_save_config
        app_module.auto_scheduler.status_payload = self._original_status_payload
        app_module.auto_scheduler.run_now = self._original_run_now

    async def test_get_current_session_requires_token(self):
        request = Request({"type": "http", "headers": []})

        with self.assertRaises(HTTPException) as context:
            await app_module.get_current_session(request)

        self.assertEqual(context.exception.status_code, 401)
        self.assertIn("Token", context.exception.detail)

    async def test_get_auto_schedule_session_returns_authenticated_session(self):
        session = SimpleNamespace(cpf="12345678901", nome="Tester")

        response = await app_module.get_auto_schedule_session(session)

        self.assertIs(response, session)

    async def test_auto_schedule_config_returns_payload_for_current_session(self):
        def fake_config_payload(cpf: str):
            self.assertEqual(cpf, "12345678901")
            return {
                "enabled": True,
                "weekly_rules": make_weekly_rules(MON=["AL"], THU=["AL"]),
                "duration_mode": "30d",
                "active_until": date(2026, 4, 21),
                "updated_at": datetime(2026, 3, 22, 10, 0, tzinfo=TZ),
                "last_successful_run_at": None,
                "has_credentials": True,
                "credentials_updated_at": datetime(2026, 3, 22, 9, 30, tzinfo=TZ),
                "primary_day": "SAT",
                "primary_run_time": "09:12",
                "fallback_day": "SUN",
                "fallback_run_time": "09:12",
            }

        app_module.auto_scheduler.config_payload = fake_config_payload

        response = await app_module.auto_schedule_config(
            SimpleNamespace(cpf="12345678901")
        )

        self.assertTrue(response.enabled)
        self.assertTrue(response.has_credentials)
        self.assertEqual(response.primary_day, "SAT")
        self.assertEqual(response.primary_run_time, "09:12")
        self.assertEqual(response.weekly_rules["MON"], ["AL"])
        self.assertEqual(response.weekly_rules["THU"], ["AL"])

    async def test_auto_schedule_save_config_uses_scheduler_for_current_session(self):
        def fake_save_config(cpf: str, **kwargs):
            self.assertEqual(cpf, "12345678901")
            self.assertTrue(kwargs["enabled"])
            self.assertEqual(kwargs["weekly_rules"]["MON"], ["AL"])
            self.assertEqual(kwargs["weekly_rules"]["THU"], ["JA"])
            self.assertEqual(kwargs["orbital_password"], "orbital-secret")
            self.assertFalse(kwargs["clear_saved_credentials"])
            return {
                "enabled": True,
                "weekly_rules": make_weekly_rules(MON=["AL"], THU=["JA"]),
                "duration_mode": "90d",
                "active_until": date(2026, 6, 20),
                "updated_at": datetime(2026, 3, 22, 10, 0, tzinfo=TZ),
                "last_successful_run_at": None,
                "has_credentials": True,
                "credentials_updated_at": datetime(2026, 3, 22, 10, 0, tzinfo=TZ),
                "primary_day": "SAT",
                "primary_run_time": "11:20",
                "fallback_day": "SUN",
                "fallback_run_time": "11:20",
            }

        app_module.auto_scheduler.save_config = fake_save_config

        response = await app_module.auto_schedule_save_config(
            AutoScheduleConfigRequest(
                enabled=True,
                weekly_rules=make_weekly_rules(MON=["AL"], THU=["JA"]),
                duration_mode="90d",
                orbital_password="orbital-secret",
            ),
            SimpleNamespace(cpf="12345678901"),
        )

        self.assertEqual(response.duration_mode, "90d")
        self.assertTrue(response.has_credentials)
        self.assertEqual(response.primary_run_time, "11:20")

    async def test_auto_schedule_status_returns_updated_payload(self):
        def fake_status_payload(cpf: str):
            self.assertEqual(cpf, "12345678901")
            return {
                "enabled": True,
                "dry_run": True,
                "running": False,
                "timezone": "America/Sao_Paulo",
                "weekly_rules": make_weekly_rules(MON=["AL"], THU=["JA"]),
                "duration_mode": "30d",
                "active_until": date(2026, 4, 21),
                "updated_at": datetime(2026, 3, 22, 10, 0, tzinfo=TZ),
                "last_successful_run_at": datetime(2026, 3, 22, 8, 0, tzinfo=TZ),
                "primary_day": "SAT",
                "primary_run_time": "09:12",
                "fallback_day": "SUN",
                "fallback_run_time": "09:12",
                "has_credentials": True,
                "credentials_updated_at": datetime(2026, 3, 22, 7, 45, tzinfo=TZ),
                "next_run_at": datetime(2026, 3, 28, 9, 12, tzinfo=TZ),
                "last_run": None,
            }

        app_module.auto_scheduler.status_payload = fake_status_payload

        response = await app_module.auto_schedule_status(
            SimpleNamespace(cpf="12345678901")
        )

        self.assertEqual(response.primary_day, "SAT")
        self.assertEqual(response.fallback_day, "SUN")
        self.assertTrue(response.has_credentials)
        self.assertEqual(response.weekly_rules["THU"], ["JA"])

    async def test_auto_schedule_run_uses_scheduler_for_current_session(self):
        async def fake_run_now(cpf: str, *, trigger: str, force: bool):
            self.assertEqual(cpf, "12345678901")
            self.assertEqual(trigger, "manual")
            self.assertTrue(force)
            return {
                "trigger": trigger,
                "enabled": True,
                "dry_run": True,
                "started_at": datetime(2026, 3, 22, 10, 0, tzinfo=TZ),
                "finished_at": datetime(2026, 3, 22, 10, 1, tzinfo=TZ),
                "success": True,
                "message": "Dry run completed with 1 candidate(s).",
                "used_existing_session": True,
                "login_performed": False,
                "candidates_count": 1,
                "scheduled_count": 0,
                "already_scheduled_count": 0,
                "skipped_count": 0,
                "errors": [],
                "last_error": None,
            }

        app_module.auto_scheduler.run_now = fake_run_now

        response = await app_module.auto_schedule_run(
            SimpleNamespace(cpf="12345678901")
        )

        self.assertEqual(response.trigger, "manual")
        self.assertTrue(response.success)
        self.assertTrue(response.used_existing_session)


if __name__ == "__main__":
    unittest.main()
