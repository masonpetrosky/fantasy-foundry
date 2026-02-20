import os
import unittest
from unittest.mock import patch

from backend.core.settings import load_settings_from_env


class AppSettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings_from_env()

        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.calculator_job_workers, 2)
        self.assertTrue(settings.enable_startup_calc_prewarm)
        self.assertEqual(settings.cors_allow_origins, ("*",))
        self.assertEqual(settings.rate_limit_bucket_cleanup_interval_seconds, 60.0)
        self.assertEqual(settings.projection_rate_limit_per_minute, 120)
        self.assertEqual(settings.projection_export_rate_limit_per_minute, 30)
        self.assertFalse(settings.require_calculate_auth)
        self.assertEqual(settings.calculate_api_keys_raw, "")

    def test_overrides_and_bounds(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FF_ENV": "production",
                "FF_CALC_JOB_WORKERS": "0",
                "FF_PREWARM_DEFAULT_CALC": "false",
                "FF_RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS": "2",
                "FF_CORS_ALLOW_ORIGINS": "https://a.example, https://b.example",
                "FF_PROJ_RATE_LIMIT_PER_MINUTE": "0",
                "FF_EXPORT_RATE_LIMIT_PER_MINUTE": "0",
                "FF_REQUIRE_CALCULATE_AUTH": "true",
                "FF_CALCULATE_API_KEYS": "key-a,key-b",
            },
            clear=True,
        ):
            settings = load_settings_from_env()

        self.assertEqual(settings.environment, "production")
        self.assertEqual(settings.calculator_job_workers, 1)
        self.assertFalse(settings.enable_startup_calc_prewarm)
        self.assertEqual(settings.rate_limit_bucket_cleanup_interval_seconds, 5.0)
        self.assertEqual(settings.cors_allow_origins, ("https://a.example", "https://b.example"))
        self.assertEqual(settings.projection_rate_limit_per_minute, 1)
        self.assertEqual(settings.projection_export_rate_limit_per_minute, 1)
        self.assertTrue(settings.require_calculate_auth)
        self.assertEqual(settings.calculate_api_keys_raw, "key-a,key-b")


if __name__ == "__main__":
    unittest.main()
