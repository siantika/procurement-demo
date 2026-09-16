"""Management command for reproducible optimizer measurements."""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.optimization.benchmark import run_benchmark


class Command(BaseCommand):
    help = "Benchmark greedy-bounded-v1 with deterministic synthetic data."

    def add_arguments(self, parser):
        parser.add_argument("--items", type=int, default=100)
        parser.add_argument("--offers-per-item", type=int, default=50)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--warmups", type=int, default=2)
        parser.add_argument("--runs", type=int, default=10)
        parser.add_argument(
            "--max-results",
            type=int,
            default=settings.OPTIMIZER_MAX_RESULTS,
        )
        parser.add_argument(
            "--exploration-limit",
            type=int,
            default=settings.OPTIMIZER_EXPLORATION_LIMIT,
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
        )

    def handle(self, *args, **options):
        self._validate_options(options)
        report = run_benchmark(
            items=options["items"],
            offers_per_item=options["offers_per_item"],
            seed=options["seed"],
            warmups=options["warmups"],
            runs=options["runs"],
            max_results=options["max_results"],
            exploration_limit=options["exploration_limit"],
        )
        if options["format"] == "json":
            self.stdout.write(json.dumps(report, sort_keys=True))
            return
        self._write_text_report(report)

    @staticmethod
    def _validate_options(options):
        limits = (
            ("items", 1, settings.OPTIMIZER_MAX_ITEMS),
            (
                "offers_per_item",
                1,
                settings.OPTIMIZER_MAX_OFFERS_PER_ITEM,
            ),
            ("warmups", 0, 20),
            ("runs", 1, 100),
            ("max_results", 1, settings.OPTIMIZER_MAX_RESULTS),
            ("exploration_limit", 1, 100_000),
        )
        for key, minimum, maximum in limits:
            value = options[key]
            if not minimum <= value <= maximum:
                option = key.replace("_", "-")
                raise CommandError(
                    f"--{option} harus antara {minimum} dan {maximum}."
                )

    def _write_text_report(self, report):
        parameters = report["parameters"]
        self.stdout.write(
            "Optimizer benchmark: "
            f"{parameters['items']} items × "
            f"{parameters['offers_per_item']} offers "
            f"({parameters['total_offers']} total), "
            f"seed={parameters['seed']}"
        )
        for measurement in report["runs"]:
            self.stdout.write(
                f"Run {measurement['run']:02d}: "
                f"{measurement['duration_ms']:.3f} ms, "
                f"explored={measurement['explored_vectors']}, "
                "discovered="
                f"{measurement['valid_candidates_discovered']}/"
                f"{measurement['rejected_candidates_discovered']}, "
                f"results={measurement['result_count']}, "
                f"validation={measurement['validation_status']}"
            )
        summary = report["summary"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Median={summary['median_ms']:.3f} ms, "
                f"p95={summary['p95_ms']:.3f} ms, "
                "cv="
                f"{summary['coefficient_of_variation_percent']:.2f}%, "
                f"peak_python={summary['peak_python_allocated_bytes']} "
                "bytes, deterministic=yes, validation=valid"
            )
        )
