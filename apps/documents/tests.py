import hashlib
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.approval.services import approve_bid
from apps.bids.choices import BidStatus
from apps.bids.tests import BidFixtureMixin
from apps.notifications.models import Notification
from apps.signatures.services import sign_bid

from .choices import GenerationJobStatus
from .models import DocumentGenerationJob, FinalDocument
from .renderers import render_pdf_v1
from .services import (
    claim_generation_job,
    complete_generation_job,
    fail_generation_job,
    get_authorized_document,
    request_finalization,
)
from .signature_images import load_signature_image_data_uri
from .storage import PrivateStorageError, StoredObject
from .tasks import reconcile_pending_jobs


class DocumentFixtureMixin(BidFixtureMixin):
    def signed_bid(self):
        _proposal, revision = self.submitted_bid()
        approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )
        revision.refresh_from_db()
        sign_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )
        revision.refresh_from_db()
        return revision

    def pending_job(self):
        revision = self.signed_bid()
        job = request_finalization(
            actor=self.staff,
            revision_id=revision.pk,
            correlation_id=self.correlation_id(),
        )
        return revision, job

    def complete_job(self):
        revision, job = self.pending_job()
        claimed = claim_generation_job(
            job_id=job.pk, correlation_id=self.correlation_id()
        )
        content = b"%PDF-1.7\nfixture"
        checksum = hashlib.sha256(content).hexdigest()
        object_key = (
            f"documents/{job.bid_revision_id}/"
            f"{job.bid_revision.revision_number}/"
            f"{job.document_version}/{job.pk}.pdf"
        )
        stored = StoredObject(
            object_key=object_key,
            version_id="object-v1",
            content_type="application/pdf",
            size=len(content),
        )
        with (
            patch(
                "apps.documents.services.stat_private_object",
                return_value=stored,
            ),
            patch(
                "apps.documents.services.read_private_object",
                return_value=content,
            ),
        ):
            document = complete_generation_job(
                job_id=claimed.pk,
                object_key=stored.object_key,
                object_version_id=stored.version_id,
                size_bytes=len(content),
                sha256=checksum,
                correlation_id=self.correlation_id(),
            )
        revision.refresh_from_db()
        job.refresh_from_db()
        return revision, job, document, content


class DocumentServiceTests(DocumentFixtureMixin, TestCase):
    def test_request_keeps_bid_signed_until_pdf_verified(self):
        revision, job = self.pending_job()

        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.SIGNED)
        self.assertEqual(job.status, GenerationJobStatus.PENDING)
        self.assertEqual(job.document_version, 1)
        self.assertEqual(len(job.input_hash), 64)

    def test_finalization_snapshot_freezes_signature_image_metadata(self):
        _proposal, revision = self.submitted_bid()
        approve_bid(
            actor=self.manager,
            revision_id=revision.pk,
            expected_version=revision.version,
            correlation_id=self.correlation_id(),
        )
        revision.refresh_from_db()
        buffer = BytesIO()
        Image.new("RGB", (400, 160), "white").save(
            buffer, format="PNG"
        )
        content = buffer.getvalue()
        upload = SimpleUploadedFile(
            "signature.png", content, content_type="image/png"
        )
        stored = StoredObject(
            object_key=f"signatures/{revision.pk}/signature.png",
            version_id="signature-version-1",
            content_type="image/png",
            size=len(content),
        )
        with patch(
            "apps.signatures.services.store_private_object",
            return_value=stored,
        ):
            signature = sign_bid(
                actor=self.manager,
                revision_id=revision.pk,
                expected_version=revision.version,
                signature_image=upload,
                correlation_id=self.correlation_id(),
            )
        job = request_finalization(
            actor=self.staff,
            revision_id=revision.pk,
            correlation_id=self.correlation_id(),
        )

        frozen = job.input_snapshot["signature"]
        self.assertEqual(
            frozen["image_object_key"], signature.image_object_key
        )
        self.assertEqual(frozen["image_sha256"], signature.image_sha256)

    def test_only_staff_can_request_finalization(self):
        revision = self.signed_bid()
        with self.assertRaises(PermissionDenied):
            request_finalization(
                actor=self.manager,
                revision_id=revision.pk,
                correlation_id=self.correlation_id(),
            )

    def test_duplicate_finalization_request_returns_active_job(self):
        revision, first = self.pending_job()

        second = request_finalization(
            actor=self.staff,
            revision_id=revision.pk,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            revision.generation_jobs.filter(
                status=GenerationJobStatus.PENDING
            ).count(),
            1,
        )

    def test_failed_job_leaves_bid_signed(self):
        revision, job = self.pending_job()
        claim_generation_job(
            job_id=job.pk, correlation_id=self.correlation_id()
        )

        fail_generation_job(
            job_id=job.pk,
            safe_error_code="DOCUMENT_TECHNICAL_ERROR",
            safe_error_message="Dokumen gagal dibuat.",
            diagnostic_reference="diagnostic-test",
            correlation_id=self.correlation_id(),
        )

        revision.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.SIGNED)
        self.assertEqual(job.status, GenerationJobStatus.FAILED)
        self.assertEqual(Notification.objects.count(), 1)

    def test_completion_finalizes_bid_and_is_idempotent(self):
        revision, job, document, content = self.complete_job()

        self.assertEqual(revision.status, BidStatus.FINALIZED)
        self.assertEqual(job.status, GenerationJobStatus.COMPLETED)
        self.assertEqual(FinalDocument.objects.count(), 1)
        stored = StoredObject(
            object_key=document.object_key,
            version_id=document.object_version_id,
            content_type="application/pdf",
            size=len(content),
        )
        with (
            patch(
                "apps.documents.services.stat_private_object",
                return_value=stored,
            ),
            patch(
                "apps.documents.services.read_private_object",
                return_value=content,
            ),
        ):
            duplicate = complete_generation_job(
                job_id=job.pk,
                object_key=document.object_key,
                object_version_id=document.object_version_id,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
                correlation_id=self.correlation_id(),
            )
        self.assertEqual(duplicate.pk, document.pk)
        self.assertEqual(FinalDocument.objects.count(), 1)

    def test_invalid_object_cannot_finalize_bid(self):
        revision, job = self.pending_job()
        claim_generation_job(
            job_id=job.pk, correlation_id=self.correlation_id()
        )
        stored = StoredObject(
            object_key=(
                f"documents/{job.bid_revision_id}/"
                f"{job.bid_revision.revision_number}/"
                f"{job.document_version}/{job.pk}.pdf"
            ),
            version_id=None,
            content_type="application/pdf",
            size=5,
        )
        with (
            patch(
                "apps.documents.services.stat_private_object",
                return_value=stored,
            ),
            patch(
                "apps.documents.services.read_private_object",
                return_value=b"wrong",
            ),
            self.assertRaises(ValidationError),
        ):
            complete_generation_job(
                job_id=job.pk,
                object_key=stored.object_key,
                object_version_id=None,
                size_bytes=5,
                sha256=hashlib.sha256(b"wrong").hexdigest(),
                correlation_id=self.correlation_id(),
            )
        revision.refresh_from_db()
        self.assertEqual(revision.status, BidStatus.SIGNED)
        self.assertFalse(FinalDocument.objects.exists())

    def test_regeneration_uses_new_version_and_number(self):
        revision, first_job, _document, _content = self.complete_job()

        second = request_finalization(
            actor=self.staff,
            revision_id=revision.pk,
            correlation_id=self.correlation_id(),
        )

        self.assertEqual(second.document_version, 2)
        self.assertNotEqual(
            first_job.input_snapshot["document"]["document_number"],
            second.input_snapshot["document"]["document_number"],
        )

    def test_final_document_is_immutable(self):
        _revision, _job, document, _content = self.complete_job()
        document.document_number = "changed"
        with self.assertRaises(ValidationError):
            document.save()
        with self.assertRaises(ValidationError):
            FinalDocument.objects.filter(pk=document.pk).delete()

    def test_pdf_renderer_produces_pdf(self):
        _revision, job = self.pending_job()
        content = render_pdf_v1(job.input_snapshot)
        self.assertTrue(content.startswith(b"%PDF-"))

    def test_verified_signature_image_is_embedded_in_pdf(self):
        _revision, job = self.pending_job()
        buffer = BytesIO()
        Image.new("RGB", (400, 160), "white").save(
            buffer, format="PNG"
        )
        image_content = buffer.getvalue()
        image_hash = hashlib.sha256(image_content).hexdigest()
        image_key = "signatures/test/signature.png"
        job.input_snapshot["signature"] = {
            **job.input_snapshot["signature"],
            "has_image": True,
            "image_object_key": image_key,
            "image_version_id": "signature-v1",
            "image_mime_type": "image/png",
            "image_size_bytes": len(image_content),
            "image_sha256": image_hash,
        }
        stored = StoredObject(
            object_key=image_key,
            version_id="signature-v1",
            content_type="image/png",
            size=len(image_content),
        )
        with (
            patch(
                "apps.documents.signature_images.stat_private_object",
                return_value=stored,
            ),
            patch(
                "apps.documents.signature_images.read_private_object",
                return_value=image_content,
            ),
        ):
            data_uri = load_signature_image_data_uri(
                job.input_snapshot
            )
        pdf = render_pdf_v1(
            job.input_snapshot, signature_image_data_uri=data_uri
        )

        self.assertTrue(data_uri.startswith("data:image/png;base64,"))
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_tampered_signature_image_is_rejected(self):
        snapshot = {
            "signature": {
                "has_image": True,
                "image_object_key": "signatures/test/image.png",
                "image_version_id": None,
                "image_mime_type": "image/png",
                "image_size_bytes": 5,
                "image_sha256": hashlib.sha256(b"wrong").hexdigest(),
            }
        }
        stored = StoredObject(
            object_key="signatures/test/image.png",
            version_id=None,
            content_type="image/png",
            size=5,
        )
        with (
            patch(
                "apps.documents.signature_images.stat_private_object",
                return_value=stored,
            ),
            patch(
                "apps.documents.signature_images.read_private_object",
                return_value=b"other",
            ),
            self.assertRaises(ValidationError),
        ):
            load_signature_image_data_uri(snapshot)

    def test_reconciliation_detects_uploaded_stale_job(self):
        _revision, job = self.pending_job()
        claim_generation_job(
            job_id=job.pk, correlation_id=self.correlation_id()
        )
        DocumentGenerationJob.objects.filter(pk=job.pk).update(
            started_at=timezone.now() - timedelta(minutes=5)
        )
        content = b"%PDF-1.7\norphan"
        stored = StoredObject(
            object_key=(
                f"documents/{job.bid_revision_id}/"
                f"{job.bid_revision.revision_number}/"
                f"{job.document_version}/{job.pk}.pdf"
            ),
            version_id="recovered-v1",
            content_type="application/pdf",
            size=len(content),
        )
        with (
            patch(
                "apps.documents.tasks.stat_private_object",
                return_value=stored,
            ),
            patch(
                "apps.documents.tasks.read_private_object",
                return_value=content,
            ),
            patch(
                "apps.documents.tasks.complete_generation_job"
            ) as complete,
        ):
            count = reconcile_pending_jobs.run()

        self.assertEqual(count, 1)
        complete.assert_called_once()


class DocumentAuthorizationTests(DocumentFixtureMixin, TestCase):
    def test_staff_and_manager_can_download_but_admin_cannot(self):
        _revision, _job, document, content = self.complete_job()
        with patch(
            "apps.documents.services.read_private_object",
            return_value=content,
        ):
            returned, returned_content = get_authorized_document(
                actor=self.staff, document_id=document.pk
            )
            self.assertEqual(returned.pk, document.pk)
            self.assertEqual(returned_content, content)
            get_authorized_document(
                actor=self.manager, document_id=document.pk
            )
            with self.assertRaises(PermissionDenied):
                get_authorized_document(
                    actor=self.admin, document_id=document.pk
                )

    def test_anonymous_download_redirects_to_login(self):
        _revision, _job, document, _content = self.complete_job()
        response = self.client.get(
            reverse("documents:download", args=[document.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_staff_download_has_private_security_headers(self):
        _revision, _job, document, content = self.complete_job()
        self.client.force_login(self.staff)
        with patch(
            "apps.documents.services.read_private_object",
            return_value=content,
        ):
            response = self.client.get(
                reverse("documents:download", args=[document.pk])
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_storage_failure_returns_safe_response(self):
        _revision, _job, document, _content = self.complete_job()
        self.client.force_login(self.staff)
        with patch(
            "apps.documents.services.read_private_object",
            side_effect=PrivateStorageError("secret detail"),
        ):
            response = self.client.get(
                reverse("documents:download", args=[document.pk])
            )

        self.assertEqual(response.status_code, 409)
        self.assertContains(
            response,
            "Dokumen sementara tidak dapat diakses.",
            status_code=409,
        )
        self.assertNotContains(
            response, "secret detail", status_code=409
        )
