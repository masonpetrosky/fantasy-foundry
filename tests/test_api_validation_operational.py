import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as app_module


class OperationalHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        with app_module.REQUEST_RATE_LIMIT_LOCK:
            app_module.REQUEST_RATE_LIMIT_BUCKETS.clear()
            app_module._REQUEST_RATE_LIMIT_LAST_SWEEP_TS = 0.0

    def test_projection_read_rate_limit_returns_retry_after_header(self) -> None:
        with patch.object(app_module.PROJECTION_SERVICE._ctx.rate_limits, "read_per_minute", 1), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE,
            "projection_response",
            return_value={"total": 0, "offset": 0, "limit": 200, "data": []},
        ):
            first = self.client.get("/api/projections/bat", params={"include_dynasty": "false"})
            second = self.client.get("/api/projections/bat", params={"include_dynasty": "false"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers.get("retry-after"), "60")

    def test_projection_export_rate_limit_returns_retry_after_header(self) -> None:
        with patch.object(app_module.PROJECTION_SERVICE._ctx.rate_limits, "export_per_minute", 1), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE,
            "export_projections",
            return_value={"ok": True},
        ):
            first = self.client.get("/api/projections/export/bat", params={"format": "csv", "include_dynasty": "false"})
            second = self.client.get("/api/projections/export/bat", params={"format": "csv", "include_dynasty": "false"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers.get("retry-after"), "60")

    def test_request_id_header_is_echoed_when_provided(self) -> None:
        response = self.client.get("/api/health", headers={"X-Request-Id": "req-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-request-id"), "req-123")

    def test_ops_endpoint_returns_operational_payload(self) -> None:
        response = self.client.get("/api/ops")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertIn("build", payload)
        self.assertIn("data", payload)
        self.assertIn("runtime", payload)
        self.assertIn("rate_limits", payload)
        self.assertIn("queues", payload)
        self.assertIn("client_identity_source", payload["runtime"])
        self.assertIn("shared_remote_addr_identity_risk", payload["runtime"])
        self.assertIn("calculate_request_timeout_seconds", payload["rate_limits"])
        self.assertIn("calculate_max_active_jobs_per_ip", payload["rate_limits"])
        self.assertIn("calculate_sync_authenticated_per_minute", payload["rate_limits"])
        self.assertIn("calculate_job_create_authenticated_per_minute", payload["rate_limits"])
        self.assertIn("calculate_job_status_authenticated_per_minute", payload["rate_limits"])
        self.assertIn("calculate_max_active_jobs_total", payload["rate_limits"])
        self.assertIn("rate_limit_activity", payload["queues"])
        self.assertIn("job_pressure", payload["queues"])
        self.assertIn("totals", payload["queues"]["rate_limit_activity"])
        self.assertIn("utilization_ratio", payload["queues"]["job_pressure"])

    def test_ops_rate_limit_activity_tracks_blocked_projection_requests(self) -> None:
        with patch.object(app_module.PROJECTION_SERVICE._ctx.rate_limits, "read_per_minute", 1), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE,
            "projection_response",
            return_value={"total": 0, "offset": 0, "limit": 200, "data": []},
        ):
            first = self.client.get("/api/projections/all", params={"include_dynasty": "false"})
            second = self.client.get("/api/projections/all", params={"include_dynasty": "false"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

        ops_payload = self.client.get("/api/ops").json()
        activity = ops_payload.get("queues", {}).get("rate_limit_activity", {})
        totals = activity.get("totals", {})
        action_stats = activity.get("actions", {}).get("proj-read", {})
        self.assertGreaterEqual(int(totals.get("blocked", 0)), 1)
        self.assertGreaterEqual(int(action_stats.get("allowed", 0)), 1)
        self.assertGreaterEqual(int(action_stats.get("blocked", 0)), 1)

    def test_ops_job_pressure_reports_capacity_age_and_recent_throughput(self) -> None:
        fixed_now = datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
        now_ts = fixed_now.timestamp()
        fixed_now_iso = fixed_now.isoformat().replace("+00:00", "Z")
        cancelled_status = app_module.CALC_JOB_CANCELLED_STATUS

        def ts(offset_seconds: float) -> str:
            return (fixed_now + timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")

        jobs = {
            "queued-1": {
                "job_id": "queued-1",
                "status": "queued",
                "created_ts": now_ts - 120.0,
                "created_at": ts(-120.0),
                "started_at": None,
                "completed_at": None,
            },
            "running-1": {
                "job_id": "running-1",
                "status": "running",
                "created_ts": now_ts - 300.0,
                "created_at": ts(-300.0),
                "started_at": ts(-240.0),
                "completed_at": None,
            },
            "completed-1": {
                "job_id": "completed-1",
                "status": "completed",
                "created_ts": now_ts - 100.0,
                "created_at": ts(-100.0),
                "started_at": ts(-70.0),
                "completed_at": ts(-30.0),
            },
            "failed-1": {
                "job_id": "failed-1",
                "status": "failed",
                "created_ts": now_ts - 140.0,
                "created_at": ts(-140.0),
                "started_at": ts(-80.0),
                "completed_at": ts(-20.0),
            },
            "cancelled-1": {
                "job_id": "cancelled-1",
                "status": cancelled_status,
                "created_ts": now_ts - 110.0,
                "created_at": ts(-110.0),
                "started_at": ts(-70.0),
                "completed_at": ts(-20.0),
            },
        }

        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module,
            "_iso_now",
            return_value=fixed_now_iso,
        ), patch.object(
            app_module,
            "_cleanup_calculation_jobs",
            return_value=None,
        ), patch.dict(
            app_module.CALCULATOR_JOBS,
            jobs,
            clear=True,
        ):
            ops_payload = self.client.get("/api/ops").json()

        pressure = ops_payload.get("queues", {}).get("job_pressure", {})
        capacity_total = int(pressure.get("capacity_total", 0))
        self.assertEqual(pressure.get("active_jobs"), 2)
        self.assertEqual(pressure.get("queued_jobs"), 1)
        self.assertEqual(pressure.get("running_jobs"), 1)
        self.assertEqual(pressure.get("capacity_remaining"), max(0, capacity_total - 2))
        self.assertAlmostEqual(float(pressure.get("utilization_ratio", 0.0)), round(2 / capacity_total, 4), places=4)
        self.assertEqual(pressure.get("saturation_state"), "active")
        self.assertEqual(pressure.get("recent_window_seconds"), 900)
        self.assertEqual(pressure.get("recent_jobs_created"), 5)
        self.assertEqual(pressure.get("recent_jobs_started"), 4)
        self.assertEqual(pressure.get("recent_jobs_completed"), 1)
        self.assertEqual(pressure.get("recent_jobs_failed"), 1)
        self.assertEqual(pressure.get("recent_jobs_cancelled"), 1)
        self.assertEqual(pressure.get("recent_jobs_terminal"), 3)
        self.assertGreaterEqual(float(pressure.get("queued_oldest_age_seconds") or 0.0), 120.0)
        self.assertGreaterEqual(float(pressure.get("running_oldest_age_seconds") or 0.0), 300.0)
        self.assertGreaterEqual(float(pressure.get("running_longest_runtime_seconds") or 0.0), 240.0)
        self.assertAlmostEqual(float(pressure.get("avg_queue_wait_seconds_recent_terminal") or 0.0), 43.333, places=3)
        self.assertAlmostEqual(float(pressure.get("avg_run_duration_seconds_recent_terminal") or 0.0), 50.0, places=3)
        self.assertFalse(bool(pressure.get("alerts", {}).get("queue_wait_exceeds_request_timeout")))
        self.assertFalse(bool(pressure.get("alerts", {}).get("runtime_exceeds_request_timeout")))

    def test_validate_runtime_configuration_rejects_production_wildcard_cors(self) -> None:
        with patch.object(app_module, "APP_ENVIRONMENT", "production"), patch.object(
            app_module,
            "CORS_ALLOW_ORIGINS",
            ("*",),
        ), patch.object(
            app_module,
            "TRUST_X_FORWARDED_FOR",
            False,
        ), patch.object(
            app_module,
            "TRUSTED_PROXY_NETWORKS",
            (),
        ), patch.object(
            app_module,
            "REQUIRE_CALCULATE_AUTH",
            False,
        ), patch.object(
            app_module,
            "CALCULATE_API_KEY_IDENTITIES",
            {},
        ):
            with self.assertRaisesRegex(RuntimeError, "FF_CORS_ALLOW_ORIGINS"):
                app_module._validate_runtime_configuration()

    def test_validate_runtime_configuration_rejects_xff_without_trusted_proxy_cidrs(self) -> None:
        with patch.object(app_module, "APP_ENVIRONMENT", "production"), patch.object(
            app_module,
            "CORS_ALLOW_ORIGINS",
            ("https://fantasy-foundry.com",),
        ), patch.object(
            app_module,
            "TRUST_X_FORWARDED_FOR",
            True,
        ), patch.object(
            app_module,
            "TRUSTED_PROXY_NETWORKS",
            (),
        ), patch.object(
            app_module,
            "REQUIRE_CALCULATE_AUTH",
            False,
        ), patch.object(
            app_module,
            "CALCULATE_API_KEY_IDENTITIES",
            {},
        ):
            with self.assertRaisesRegex(RuntimeError, "FF_TRUST_X_FORWARDED_FOR"):
                app_module._validate_runtime_configuration()

    def test_validate_runtime_configuration_rejects_auth_without_keys(self) -> None:
        with patch.object(app_module, "APP_ENVIRONMENT", "production"), patch.object(
            app_module,
            "CORS_ALLOW_ORIGINS",
            ("https://fantasy-foundry.com",),
        ), patch.object(
            app_module,
            "TRUST_X_FORWARDED_FOR",
            False,
        ), patch.object(
            app_module,
            "TRUSTED_PROXY_NETWORKS",
            (),
        ), patch.object(
            app_module,
            "REQUIRE_CALCULATE_AUTH",
            True,
        ), patch.object(
            app_module,
            "CALCULATE_API_KEY_IDENTITIES",
            {},
        ):
            with self.assertRaisesRegex(RuntimeError, "FF_REQUIRE_CALCULATE_AUTH"):
                app_module._validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
