from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .management.commands.smoke_demo import Command


class SmokeDemoCommandTests(SimpleTestCase):
    def test_refuses_non_demo_environment(self):
        with self.assertRaises(CommandError):
            call_command("smoke_demo", stdout=StringIO())

    @override_settings(APP_ENV="demo")
    def test_rejects_run_count_outside_rehearsal_limit(self):
        with self.assertRaises(CommandError):
            call_command("smoke_demo", runs=4, stdout=StringIO())

    @override_settings(APP_ENV="demo")
    def test_runs_requested_rehearsal_count(self):
        outcome = {
            "purchase": "663000000.00",
            "bid": "780000000.00",
            "document_number": "BID/2026/000001/R01",
        }
        output = StringIO()
        with (
            patch.object(Command, "_load_context", return_value={}),
            patch.object(
                Command, "_run_once", return_value=outcome
            ) as run,
        ):
            call_command("smoke_demo", runs=3, stdout=output)

        self.assertEqual(run.call_count, 3)
        self.assertIn("berhasil 3 kali", output.getvalue())
