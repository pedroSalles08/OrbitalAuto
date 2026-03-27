from __future__ import annotations

import unittest

from smoke_auto_scheduler import (
    SmokeError,
    build_minimal_config,
    extract_session_source,
    validate_hosted_smoke,
)


class SmokeAutoSchedulerTests(unittest.TestCase):
    def test_build_minimal_config_sets_single_day_and_meal(self):
        payload = build_minimal_config(
            weekday="thu",
            meal="ja",
            duration_mode="90d",
        )

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["duration_mode"], "90d")
        self.assertEqual(payload["weekly_rules"]["THU"], ["JA"])
        self.assertEqual(payload["weekly_rules"]["MON"], [])
        self.assertEqual(len(payload["weekly_rules"]), 7)

    def test_extract_session_source_accepts_existing_session(self):
        source = extract_session_source(
            {"used_existing_session": True, "login_performed": False}
        )

        self.assertEqual(source, "used_existing_session")

    def test_extract_session_source_requires_existing_or_login(self):
        with self.assertRaises(SmokeError):
            extract_session_source(
                {"used_existing_session": False, "login_performed": False}
            )

    def test_validate_hosted_smoke_accepts_successful_transition(self):
        summary = validate_hosted_smoke(
            baseline_status={
                "has_credentials": True,
                "last_successful_run_at": None,
            },
            run_payload={
                "trigger": "manual",
                "success": True,
                "finished_at": "2026-03-22T16:00:00-03:00",
                "used_existing_session": False,
                "login_performed": True,
            },
            follow_up_status={
                "last_successful_run_at": "2026-03-22T16:00:00-03:00",
                "next_run_at": "2026-03-29T09:00:00-03:00",
                "last_run": {
                    "trigger": "manual",
                    "finished_at": "2026-03-22T16:00:00-03:00",
                },
            },
        )

        self.assertEqual(summary["result"], "pass")
        self.assertEqual(summary["session_source"], "login_performed")

    def test_validate_hosted_smoke_requires_last_success_update(self):
        with self.assertRaises(SmokeError):
            validate_hosted_smoke(
                baseline_status={
                    "has_credentials": True,
                    "last_successful_run_at": "2026-03-22T15:00:00-03:00",
                },
                run_payload={
                    "trigger": "manual",
                    "success": True,
                    "finished_at": "2026-03-22T16:00:00-03:00",
                    "used_existing_session": True,
                    "login_performed": False,
                },
                follow_up_status={
                    "last_successful_run_at": "2026-03-22T15:00:00-03:00",
                    "last_run": {
                        "trigger": "manual",
                        "finished_at": "2026-03-22T16:00:00-03:00",
                    },
                },
            )


if __name__ == "__main__":
    unittest.main()
