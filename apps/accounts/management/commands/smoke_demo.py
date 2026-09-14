"""Run the canonical Tender-to-PDF scenario through public services."""

import time
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.approval.services import approve_bid
from apps.bids.services import (
    create_bid_proposal,
    set_target_margin,
    submit_bid,
)
from apps.documents.choices import GenerationJobStatus
from apps.documents.models import DocumentGenerationJob
from apps.documents.services import (
    get_authorized_document,
    request_finalization,
)
from apps.optimization.choices import OptimizationStatus
from apps.optimization.models import OptimizationRun
from apps.optimization.services import request_optimization
from apps.signatures.services import sign_bid
from apps.sourcing.result_services import select_result
from apps.tender.models import TenderRequest

User = get_user_model()


class Command(BaseCommand):
    help = "Run the canonical asynchronous demo smoke scenario."

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=1)

    def handle(self, *args, **options):
        if settings.APP_ENV != "demo":
            raise CommandError(
                "smoke_demo hanya boleh berjalan saat APP_ENV=demo."
            )
        run_count = options["runs"]
        if not 1 <= run_count <= 3:
            raise CommandError("--runs harus berada antara 1 dan 3.")
        context = self._load_context()
        for sequence in range(1, run_count + 1):
            result = self._run_once(context)
            self.stdout.write(
                "Smoke "
                f"{sequence}/{run_count}: "
                f"purchase={result['purchase']}, "
                f"bid={result['bid']}, "
                f"document={result['document_number']}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Primary demo smoke berhasil {run_count} kali."
            )
        )

    @staticmethod
    def _load_context():
        try:
            return {
                "staff": User.objects.get(username="demo-staff"),
                "manager": User.objects.get(username="demo-manager"),
                "tender": TenderRequest.objects.get(
                    internal_code="DEMO-TENDER-001"
                ),
            }
        except (User.DoesNotExist, TenderRequest.DoesNotExist) as error:
            raise CommandError(
                "Data canonical belum tersedia. Jalankan seed_demo."
            ) from error

    def _wait_for_run(self, run_id):
        deadline = time.monotonic() + settings.DEMO_SMOKE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            run = OptimizationRun.objects.get(pk=run_id)
            if run.status == OptimizationStatus.COMPLETED:
                return run
            if run.status == OptimizationStatus.FAILED:
                raise CommandError(
                    f"Optimization smoke gagal: {run.safe_error_code}."
                )
            time.sleep(0.25)
        raise CommandError("Optimization smoke melewati batas waktu.")

    def _wait_for_document(self, job_id):
        deadline = time.monotonic() + settings.DEMO_SMOKE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            job = DocumentGenerationJob.objects.get(pk=job_id)
            if job.status == GenerationJobStatus.COMPLETED:
                return job
            if job.status == GenerationJobStatus.FAILED:
                raise CommandError(
                    f"Document smoke gagal: {job.safe_error_code}."
                )
            time.sleep(0.25)
        raise CommandError("Document smoke melewati batas waktu.")

    def _run_once(self, context):
        staff = context["staff"]
        manager = context["manager"]
        tender = context["tender"]
        correlation_id = str(uuid.uuid4())
        run = request_optimization(
            actor=staff,
            tender_request_id=tender.pk,
            correlation_id=correlation_id,
        )
        run = self._wait_for_run(run.pk)
        result = run.procurement_results.get(rank=1)
        if result.total_purchase != Decimal("663000000.00"):
            raise CommandError("Total purchase smoke tidak canonical.")
        select_result(
            actor=staff,
            result_id=result.pk,
            correlation_id=correlation_id,
        )
        _proposal, revision = create_bid_proposal(
            actor=staff,
            tender_request_id=tender.pk,
            correlation_id=correlation_id,
        )
        revision = set_target_margin(
            actor=staff,
            revision_id=revision.pk,
            expected_version=revision.version,
            target_margin_percent=Decimal("15.0000"),
            correlation_id=correlation_id,
        )
        if revision.total_bid_value != Decimal("780000000.00"):
            raise CommandError("Total Bid smoke tidak canonical.")
        revision = submit_bid(
            actor=staff,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=correlation_id,
        )
        approve_bid(
            actor=manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=correlation_id,
        )
        revision.refresh_from_db()
        sign_bid(
            actor=manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=correlation_id,
        )
        job = request_finalization(
            actor=staff,
            revision_id=revision.pk,
            correlation_id=correlation_id,
        )
        job = self._wait_for_document(job.pk)
        document, content = get_authorized_document(
            actor=staff, document_id=job.final_document.pk
        )
        if not content.startswith(b"%PDF-"):
            raise CommandError("Output smoke bukan PDF valid.")
        return {
            "purchase": result.total_purchase,
            "bid": revision.total_bid_value,
            "document_number": document.document_number,
        }
