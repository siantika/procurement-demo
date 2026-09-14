"""Safely remove only the canonical demo namespace."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.approval.models import ApprovalDecision
from apps.audit.models import AuditEvent
from apps.bids.models import (
    BidProposal,
    BidProposalItem,
    BidProposalRevision,
)
from apps.catalog.models import Product, Supplier
from apps.documents.models import DocumentGenerationJob, FinalDocument
from apps.documents.storage import (
    PrivateStorageError,
    remove_private_object,
)
from apps.notifications.models import Notification
from apps.optimization.models import (
    OptimizationCandidateRejection,
    OptimizationRun,
)
from apps.signatures.models import Signature
from apps.sourcing.models import (
    ProcurementResult,
    ProcurementResultItem,
    ProcurementResultSelection,
    SupplierAllocation,
    SupplierOffer,
)
from apps.tender.models import (
    TenderRequest,
    TenderRequestItem,
    TenderRequestRevision,
)

User = get_user_model()

DEMO_USERNAMES = ("demo-admin", "demo-staff", "demo-manager")
DEMO_PRODUCT_CODES = ("PUMP-001",)
DEMO_SUPPLIER_CODES = ("SUP-A", "SUP-B", "SUP-C")
DEMO_OFFER_REFERENCES = (
    "DEMO-OFFER-A",
    "DEMO-OFFER-B",
    "DEMO-OFFER-C",
)
DEMO_TENDER_CODES = ("DEMO-TENDER-001",)


def _raw_delete(queryset):
    return queryset._raw_delete(queryset.db)  # noqa: SLF001


class Command(BaseCommand):
    help = "Remove only canonical demo data after explicit confirmation."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", required=True)

    def handle(self, *args, **options):
        if settings.APP_ENV != "demo":
            raise CommandError(
                "reset_demo_data hanya boleh berjalan saat APP_ENV=demo."
            )
        if options["confirm"] != "DEMO_ONLY":
            raise CommandError(
                "Konfirmasi tidak valid. Gunakan --confirm DEMO_ONLY."
            )

        object_keys, counts = self._delete_database_rows()
        storage_failures = self._delete_objects(object_keys)
        summary = ", ".join(
            f"{name}={count}" for name, count in counts.items()
        )
        self.stdout.write(f"Reset data demo selesai: {summary}.")
        self.stdout.write(
            f"Object dihapus={len(object_keys) - storage_failures}, "
            f"gagal={storage_failures}."
        )
        if storage_failures:
            raise CommandError(
                "Database sudah direset, tetapi sebagian object private "
                "gagal dibersihkan. Periksa MinIO sebelum seed ulang."
            )

    @transaction.atomic
    def _delete_database_rows(self):
        users = User.objects.filter(username__in=DEMO_USERNAMES)
        user_ids = list(users.values_list("pk", flat=True))
        tenders = TenderRequest.objects.filter(
            internal_code__in=DEMO_TENDER_CODES
        )
        tender_ids = list(tenders.values_list("pk", flat=True))
        revisions = TenderRequestRevision.objects.filter(
            tender_request_id__in=tender_ids
        )
        revision_ids = list(revisions.values_list("pk", flat=True))
        results = ProcurementResult.objects.filter(
            tender_revision_id__in=revision_ids
        )
        result_ids = list(results.values_list("pk", flat=True))
        proposals = BidProposal.objects.filter(
            tender_request_id__in=tender_ids
        )
        proposal_ids = list(proposals.values_list("pk", flat=True))
        bid_revisions = BidProposalRevision.objects.filter(
            bid_proposal_id__in=proposal_ids
        )
        bid_revision_ids = list(
            bid_revisions.values_list("pk", flat=True)
        )
        jobs = DocumentGenerationJob.objects.filter(
            bid_revision_id__in=bid_revision_ids
        )
        job_ids = list(jobs.values_list("pk", flat=True))
        final_documents = FinalDocument.objects.filter(
            generation_job_id__in=job_ids
        )
        signatures = Signature.objects.filter(
            bid_revision_id__in=bid_revision_ids
        )
        object_keys = list(
            final_documents.values_list("object_key", flat=True)
        ) + list(
            signatures.exclude(image_object_key__isnull=True).values_list(
                "image_object_key", flat=True
            )
        )
        entity_ids = set(
            tender_ids
            + revision_ids
            + result_ids
            + proposal_ids
            + bid_revision_ids
            + job_ids
        )

        counts = {}
        counts["notifications"] = _raw_delete(
            Notification.objects.filter(recipient_id__in=user_ids)
        )
        counts["audit"] = _raw_delete(
            AuditEvent.objects.filter(
                Q(actor_id__in=user_ids) | Q(entity_id__in=entity_ids)
            )
        )
        counts["final_documents"] = _raw_delete(final_documents)
        counts["generation_jobs"] = _raw_delete(jobs)
        counts["signatures"] = _raw_delete(signatures)
        counts["approvals"] = _raw_delete(
            ApprovalDecision.objects.filter(
                bid_revision_id__in=bid_revision_ids
            )
        )
        counts["bid_items"] = _raw_delete(
            BidProposalItem.objects.filter(
                bid_revision_id__in=bid_revision_ids
            )
        )
        counts["bid_revisions"] = _raw_delete(bid_revisions)
        counts["bids"] = _raw_delete(proposals)
        counts["selections"] = _raw_delete(
            ProcurementResultSelection.objects.filter(
                tender_request_id__in=tender_ids
            )
        )
        result_items = ProcurementResultItem.objects.filter(
            procurement_result_id__in=result_ids
        )
        result_item_ids = list(
            result_items.values_list("pk", flat=True)
        )
        counts["allocations"] = _raw_delete(
            SupplierAllocation.objects.filter(
                procurement_result_item_id__in=result_item_ids
            )
        )
        counts["result_items"] = _raw_delete(result_items)
        counts["results"] = _raw_delete(results)
        runs = OptimizationRun.objects.filter(
            tender_request_id__in=tender_ids
        )
        run_ids = list(runs.values_list("pk", flat=True))
        counts["candidate_rejections"] = _raw_delete(
            OptimizationCandidateRejection.objects.filter(
                optimization_run_id__in=run_ids
            )
        )
        counts["optimization_runs"] = _raw_delete(runs)
        counts["tender_items"] = _raw_delete(
            TenderRequestItem.objects.filter(
                tender_revision_id__in=revision_ids
            )
        )
        counts["tender_revisions"] = _raw_delete(revisions)
        counts["tenders"] = _raw_delete(tenders)
        counts["offers"] = _raw_delete(
            SupplierOffer.objects.filter(
                supplier_reference__in=DEMO_OFFER_REFERENCES
            )
        )
        counts["products"] = _raw_delete(
            Product.objects.filter(code__in=DEMO_PRODUCT_CODES)
        )
        counts["suppliers"] = _raw_delete(
            Supplier.objects.filter(code__in=DEMO_SUPPLIER_CODES)
        )
        counts["users"] = _raw_delete(users)
        return object_keys, counts

    @staticmethod
    def _delete_objects(object_keys):
        failures = 0
        for object_key in object_keys:
            try:
                remove_private_object(object_key)
            except PrivateStorageError:
                failures += 1
        return failures
