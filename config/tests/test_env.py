from unittest import TestCase
from unittest.mock import patch

from config.env import database_from_url, env_bool, env_csv


class DatabaseFromUrlTests(TestCase):
    def test_parses_local_socket_url(self):
        config = database_from_url("postgresql:///procurement")

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "procurement")
        self.assertEqual(config["USER"], "")
        self.assertEqual(config["HOST"], "")
        self.assertEqual(config["PORT"], "")

    def test_parses_credentials_host_port_and_sslmode(self):
        config = database_from_url(
            "postgresql://app%40user:secret%2Fvalue@db:5433/procurement?sslmode=require",
            conn_max_age=60,
        )

        self.assertEqual(config["USER"], "app@user")
        self.assertEqual(config["PASSWORD"], "secret/value")
        self.assertEqual(config["HOST"], "db")
        self.assertEqual(config["PORT"], "5433")
        self.assertEqual(config["CONN_MAX_AGE"], 60)
        self.assertEqual(config["OPTIONS"], {"sslmode": "require"})

    def test_rejects_non_postgresql_url(self):
        with self.assertRaisesRegex(RuntimeError, "postgres"):
            database_from_url("sqlite:///db.sqlite3")

    def test_rejects_missing_database_name(self):
        with self.assertRaisesRegex(RuntimeError, "database name"):
            database_from_url("postgresql://localhost")


class EnvironmentValueTests(TestCase):
    def test_parses_supported_boolean_values(self):
        for raw_value in ("1", "true", "YES", "on"):
            with (
                self.subTest(raw_value=raw_value),
                patch.dict(
                    "os.environ",
                    {"FEATURE_FLAG": raw_value},
                ),
            ):
                self.assertTrue(env_bool("FEATURE_FLAG", default=False))

        for raw_value in ("0", "false", "NO", "off"):
            with (
                self.subTest(raw_value=raw_value),
                patch.dict(
                    "os.environ",
                    {"FEATURE_FLAG": raw_value},
                ),
            ):
                self.assertFalse(env_bool("FEATURE_FLAG", default=True))

    def test_rejects_invalid_boolean(self):
        with (
            patch.dict("os.environ", {"FEATURE_FLAG": "sometimes"}),
            self.assertRaisesRegex(RuntimeError, "Invalid boolean"),
        ):
            env_bool("FEATURE_FLAG", default=False)

    def test_parses_and_trims_csv_values(self):
        with patch.dict(
            "os.environ", {"HOSTS": "example.com, api.example.com, "}
        ):
            self.assertEqual(
                env_csv("HOSTS"), ["example.com", "api.example.com"]
            )

    def test_rejects_empty_required_csv(self):
        with (
            patch.dict("os.environ", {"HOSTS": ""}),
            self.assertRaisesRegex(RuntimeError, "HOSTS"),
        ):
            env_csv("HOSTS", required=True)
