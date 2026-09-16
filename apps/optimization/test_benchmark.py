import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .benchmark import build_synthetic_dataset, run_benchmark


class OptimizerBenchmarkTests(SimpleTestCase):
    def test_synthetic_dataset_is_seeded_and_reproducible(self):
        first = build_synthetic_dataset(
            items=3, offers_per_item=4, seed=42
        )
        second = build_synthetic_dataset(
            items=3, offers_per_item=4, seed=42
        )
        different = build_synthetic_dataset(
            items=3, offers_per_item=4, seed=43
        )

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertEqual(sum(len(item.offers) for item in first), 12)

    def test_report_is_deterministic_and_validated(self):
        report = run_benchmark(
            items=3,
            offers_per_item=4,
            seed=42,
            warmups=0,
            runs=2,
            max_results=3,
            exploration_limit=10,
        )

        self.assertEqual(report["parameters"]["total_offers"], 12)
        self.assertTrue(report["summary"]["deterministic"])
        self.assertEqual(
            report["summary"]["validation_status"], "valid"
        )
        self.assertEqual(
            len(
                {
                    measurement["result_checksum"]
                    for measurement in report["runs"]
                }
            ),
            1,
        )
        self.assertTrue(
            all(
                measurement["explored_vectors"] == 10
                for measurement in report["runs"]
            )
        )

    def test_json_command_exposes_measurement_schema(self):
        output = StringIO()

        call_command(
            "benchmark_optimizer",
            items=2,
            offers_per_item=3,
            seed=42,
            warmups=0,
            runs=1,
            max_results=2,
            exploration_limit=5,
            format="json",
            stdout=output,
        )

        report = json.loads(output.getvalue())
        self.assertEqual(
            report["benchmark"],
            "procurement-optimizer-performance",
        )
        self.assertIn("median_ms", report["summary"])
        self.assertIn("peak_python_allocated_bytes", report["summary"])
        self.assertEqual(
            report["runs"][0]["validation_status"], "valid"
        )

    def test_command_rejects_unsupported_workload(self):
        with self.assertRaises(CommandError):
            call_command(
                "benchmark_optimizer",
                items=101,
                offers_per_item=1,
                warmups=0,
                runs=1,
            )
